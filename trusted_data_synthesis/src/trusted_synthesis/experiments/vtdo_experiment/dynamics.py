from __future__ import annotations

import math
import statistics
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from trusted_synthesis.core.vtdo import VTDORoundArtifact
from trusted_synthesis.hashing import canonical_hash

from .moving_potential import run_moving_potential_tracking_experiment
from .round_io import load_vtdo_round_artifacts
from .schema import (
    AggregateMetric,
    FixedPotentialContractionSummary,
    PracticalStabilizationSummary,
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
from .statistics import aggregate_metric


@dataclass(frozen=True)
class RefinementDynamicsExecution:
    report: RefinementDynamicsReport
    controlled_rows: tuple[dict[str, object], ...]
    fixed_potential_rows: tuple[dict[str, object], ...]
    moving_potential_rows: tuple[dict[str, object], ...]
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
    """Verify the operator, moving-optimum tracking, and real feedback dynamics separately."""

    phase_values = tuple(phase_rows)
    controlled_rows, practical = _controlled_round_dynamics(
        config,
        synthetic_report,
        phase_values,
    )
    aggregates = _aggregate_controlled_rounds(config, controlled_rows)
    checkpoints = _checkpoint_summaries(config, aggregates)
    fixed_summary, fixed_rows = _fixed_potential_contraction(
        config,
        synthetic_config,
        state_catalogs,
        phase_values,
    )
    moving = run_moving_potential_tracking_experiment(
        config.moving_potential_benchmark,
        synthetic_config,
        experiment_id=experiment_id,
    )
    real_summary, real_rows = _real_round_dynamics(config)
    interpretation = (
        "The fixed-potential control verifies only the update operator. Moving potentials "
        "are evaluated against their instantaneous anchored optima using tracking error, "
        "variational-objective gain, and regret. Real feedback rounds are evaluated as "
        "finite-step tracking and stabilization, never as strict convergence."
    )
    values = {
        "experiment_id": experiment_id,
        "config_hash": canonical_hash(config, prefix="refinement_dynamics_config:"),
        "controlled_method": config.method,
        "analysis_rounds": config.analysis_rounds,
        "round_aggregates": aggregates,
        "checkpoint_summaries": checkpoints,
        "practical_stabilization": practical,
        "fixed_potential_contraction": fixed_summary,
        "moving_potential_tracking": moving.summary,
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
        moving_potential_rows=moving.rows,
        real_rows=real_rows,
    )


def _controlled_round_dynamics(
    config: RefinementDynamicsConfig,
    report: SyntheticExperimentReport,
    phase_rows: tuple[Mapping[str, float | int | str], ...],
) -> tuple[tuple[dict[str, object], ...], PracticalStabilizationSummary]:
    points_by_seed: defaultdict[int, dict[int, SyntheticMetricPoint]] = defaultdict(dict)
    for point in report.metric_points:
        if point.method == config.method and 1 <= point.round_index <= config.analysis_rounds:
            points_by_seed[point.seed][point.round_index] = point
    phase_by_seed_round: defaultdict[tuple[int, int], list[Mapping[str, float | int | str]]] = (
        defaultdict(list)
    )
    for row in phase_rows:
        seed = int(row["seed"])
        round_index = int(row["round_index"])
        if 1 <= round_index <= config.analysis_rounds:
            phase_by_seed_round[(seed, round_index)].append(row)
    expected_rounds = set(range(1, config.analysis_rounds + 1))
    if not points_by_seed:
        raise ValueError("no controlled refinement points match the configured method")

    rows: list[dict[str, object]] = []
    first_stable_round_by_seed: dict[str, int | None] = {}
    for seed, by_round in sorted(points_by_seed.items()):
        if set(by_round) != expected_rounds:
            raise ValueError(f"synthetic refinement seed {seed} has an incomplete round horizon")
        streak = 0
        first_stable_round: int | None = None
        seed_rows: list[dict[str, object]] = []
        previous_log_potential: dict[str, float] | None = None
        for round_index in range(1, config.analysis_rounds + 1):
            point = by_round[round_index]
            phase = phase_by_seed_round[(seed, round_index)]
            if not phase:
                raise ValueError(
                    f"synthetic refinement seed {seed} round {round_index} has no phase data"
                )
            prior = {str(row["state_id"]): _as_float(row["current_probability"]) for row in phase}
            next_distribution = {
                str(row["state_id"]): _as_float(row["next_probability"]) for row in phase
            }
            log_potential = {str(row["state_id"]): _as_float(row["log_potential"]) for row in phase}
            utility_before = sum(prior[key] * log_potential[key] for key in prior)
            utility_after = sum(
                next_distribution[key] * log_potential[key] for key in next_distribution
            )
            utility_delta = abs(utility_after - utility_before)
            kl_shift = _kl(next_distribution, prior)
            if not math.isclose(kl_shift, point.kl_to_previous, abs_tol=1e-10):
                raise ValueError("phase lineage disagrees with the synthetic KL transition")
            potential_drift = (
                _projective_potential_drift(log_potential, previous_log_potential)
                if previous_log_potential is not None
                else 0.0
            )
            stabilization_score = (
                kl_shift
                + config.utility_delta_weight * utility_delta
                + config.potential_drift_weight * potential_drift
            )
            stable = (
                previous_log_potential is not None
                and stabilization_score < config.stabilization_score_threshold
            )
            streak = streak + 1 if stable else 0
            if streak >= config.consecutive_stable_rounds and first_stable_round is None:
                first_stable_round = round_index
            seed_rows.append(
                {
                    "seed": seed,
                    "round_index": round_index,
                    "kl_shift": kl_shift,
                    "utility_before": utility_before,
                    "expected_log_potential": utility_after,
                    "absolute_utility_delta": utility_delta,
                    "potential_drift": potential_drift,
                    "stabilization_score": stabilization_score,
                    "entropy": point.entropy,
                    "coverage_count": point.coverage_count,
                    "stable_transition": stable,
                }
            )
            previous_log_potential = log_potential
        first_stable_round_by_seed[str(seed)] = first_stable_round
        for seed_row in seed_rows:
            seed_row["first_practical_stabilization_round"] = first_stable_round
            rows.append(seed_row)

    round_counts: dict[str, int] = {}
    for stable_round in first_stable_round_by_seed.values():
        key = "not_observed" if stable_round is None else str(stable_round)
        round_counts[key] = round_counts.get(key, 0) + 1
    stabilized = sum(value is not None for value in first_stable_round_by_seed.values())
    summary = PracticalStabilizationSummary(
        stabilization_score_threshold=config.stabilization_score_threshold,
        utility_delta_weight=config.utility_delta_weight,
        potential_drift_weight=config.potential_drift_weight,
        consecutive_rounds=config.consecutive_stable_rounds,
        evaluated_seed_count=len(first_stable_round_by_seed),
        stabilized_seed_count=stabilized,
        first_stable_round_by_seed=first_stable_round_by_seed,
        first_stable_round_counts=dict(sorted(round_counts.items())),
        practical_stabilization_observed=(stabilized == len(first_stable_round_by_seed)),
    )
    return tuple(rows), summary


def _aggregate_controlled_rounds(
    config: RefinementDynamicsConfig,
    rows: tuple[dict[str, object], ...],
) -> tuple[RefinementRoundAggregate, ...]:
    output: list[RefinementRoundAggregate] = []
    for round_index in range(1, config.analysis_rounds + 1):
        current = tuple(row for row in rows if row["round_index"] == round_index)
        if not current:
            raise ValueError(f"refinement round {round_index} has no controlled observations")
        output.append(
            RefinementRoundAggregate(
                round_index=round_index,
                transition_from_round=round_index - 1,
                kl_shift=_aggregate([_as_float(row["kl_shift"]) for row in current]),
                expected_log_potential=_aggregate(
                    [_as_float(row["expected_log_potential"]) for row in current]
                ),
                absolute_utility_delta=_aggregate(
                    [_as_float(row["absolute_utility_delta"]) for row in current]
                ),
                potential_drift=_aggregate(
                    [_as_float(row["potential_drift"]) for row in current]
                ),
                stabilization_score=_aggregate(
                    [_as_float(row["stabilization_score"]) for row in current]
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
    round_one = by_round[1].expected_log_potential.mean
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
                expected_log_potential=aggregate.expected_log_potential,
                log_potential_difference_from_round_one=(
                    aggregate.expected_log_potential.mean - round_one
                ),
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
                stabilization_eligible_sequence_count=0,
                stabilized_sequence_count=0,
                blockers=("no_real_vtdo_round_artifacts",),
            ),
            (),
        )
    loaded, load_blockers = load_vtdo_round_artifacts(config.real_round_artifact_paths)
    artifacts = list(loaded)
    blockers = list(load_blockers)
    if not artifacts:
        return (
            RealRefinementDynamicsSummary(
                status="blocked",
                configured_artifact_count=len(config.real_round_artifact_paths),
                validated_artifact_count=0,
                task_condition_count=0,
                complete_sequence_count=0,
                sequential_link_failure_count=0,
                stabilization_eligible_sequence_count=0,
                stabilized_sequence_count=0,
                blockers=tuple(sorted(set(blockers or ["no_valid_real_round_artifacts"]))),
            ),
            (),
        )

    grouped: defaultdict[str, list[VTDORoundArtifact]] = defaultdict(list)
    rows: list[dict[str, object]] = []
    row_by_round_id: dict[str, dict[str, object]] = {}
    anchor_target_by_round_id: dict[str, dict[str, float]] = {}
    log_potential_by_round_id: dict[str, dict[str, float]] = {}
    tolerance = config.moving_potential_benchmark.objective_tolerance
    for artifact in artifacts:
        grouped[artifact.task_condition_id].append(artifact)
        potentials = {item.state_id: item for item in artifact.update.state_potentials}
        potential = {state_id: item.potential for state_id, item in potentials.items()}
        prior = dict(artifact.update.prior_distribution.probabilities)
        coverage = dict(artifact.update.coverage_prior.probabilities)
        next_distribution = dict(artifact.update.next_distribution.probabilities)
        energy = artifact.update.energy_config
        utility_before = sum(prior[key] * math.log(potential[key]) for key in prior)
        utility_after = sum(
            next_distribution[key] * math.log(potential[key]) for key in next_distribution
        )
        objective_before = _proximal_objective(
            prior,
            potential,
            prior,
            coverage,
            energy.history_kl_weight,
            energy.coverage_kl_weight,
        )
        objective_after = _proximal_objective(
            next_distribution,
            potential,
            prior,
            coverage,
            energy.history_kl_weight,
            energy.coverage_kl_weight,
        )
        objective_gain = objective_after - objective_before
        proximal_target = _normalize(
            {
                state_id: prior[state_id] ** energy.history_exponent
                * coverage[state_id] ** (1.0 - energy.history_exponent)
                * potential[state_id] ** energy.energy_exponent
                for state_id in prior
            }
        )
        proximal_optimizer_kl = _kl(next_distribution, proximal_target)
        anchor_target = _normalize(
            {
                state_id: coverage[state_id]
                * potential[state_id] ** (1.0 / energy.coverage_kl_weight)
                for state_id in prior
            }
        )
        target_objective = _anchor_objective(
            anchor_target,
            potential,
            coverage,
            energy.coverage_kl_weight,
        )
        actual_anchor_objective = _anchor_objective(
            next_distribution,
            potential,
            coverage,
            energy.coverage_kl_weight,
        )
        instantaneous_regret = max(0.0, target_objective - actual_anchor_objective)
        absolute_utility_delta = abs(utility_after - utility_before)
        independently_computed_kl = _kl(next_distribution, prior)
        if not math.isclose(
            independently_computed_kl,
            artifact.update.kl_to_history,
            abs_tol=tolerance,
        ):
            blockers.append(f"round_history_kl_mismatch:{artifact.round_id}")
        if objective_gain < -tolerance:
            blockers.append(f"variational_objective_decrease:{artifact.round_id}")
        if proximal_optimizer_kl > tolerance:
            blockers.append(f"proximal_optimizer_mismatch:{artifact.round_id}")
        row = {
            "task_condition_id": artifact.task_condition_id,
            "round_index": artifact.round_index,
            "round_id": artifact.round_id,
            "kl_shift": independently_computed_kl,
            "log_potential_utility_before": utility_before,
            "log_potential_utility_after": utility_after,
            "absolute_utility_delta": absolute_utility_delta,
            "potential_drift": None,
            "stabilization_score": None,
            "variational_objective_before": objective_before,
            "variational_objective_after": objective_after,
            "variational_objective_gain": objective_gain,
            "proximal_optimizer_kl": proximal_optimizer_kl,
            "tracking_error": _kl(next_distribution, anchor_target),
            "instantaneous_regret": instantaneous_regret,
            "cumulative_regret": None,
            "target_movement_kl": None,
            "entered_state_count": 0,
            "exited_state_count": 0,
            "state_turnover_observed": False,
            "entropy": artifact.update.next_entropy,
            "coverage_count": sum(
                value > config.coverage_epsilon for value in next_distribution.values()
            ),
        }
        if artifact.round_id in row_by_round_id:
            blockers.append(f"duplicate_round_id:{artifact.round_id}")
        rows.append(row)
        row_by_round_id[artifact.round_id] = row
        anchor_target_by_round_id[artifact.round_id] = anchor_target
        log_potential_by_round_id[artifact.round_id] = {
            state_id: math.log(value) for state_id, value in potential.items()
        }

    complete = 0
    link_failures = 0
    eligible = 0
    stabilized = 0
    final_kls: list[float] = []
    final_tracking_errors: list[float] = []
    cumulative_regrets: list[float] = []
    state_entries: list[float] = []
    state_exits: list[float] = []
    expected_indices = tuple(range(config.analysis_rounds))
    for condition_id, values in sorted(grouped.items()):
        ordered = sorted(values, key=lambda item: item.round_index)
        by_index = {item.round_index: item for item in ordered}
        if len(by_index) != len(ordered):
            blockers.append(f"duplicate_round_index:{condition_id}")
            continue
        if not all(index in by_index for index in expected_indices):
            blockers.append(f"incomplete_real_refinement_sequence:{condition_id}")
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
        cumulative_regret = 0.0
        previous_support: set[str] | None = None
        previous_target: dict[str, float] | None = None
        previous_log_potential: dict[str, float] | None = None
        for artifact in sequence:
            row = row_by_round_id[artifact.round_id]
            current_support = set(artifact.update.next_distribution.probabilities)
            current_target = anchor_target_by_round_id[artifact.round_id]
            current_log_potential = log_potential_by_round_id[artifact.round_id]
            stable = False
            if previous_support is not None:
                entered = current_support - previous_support
                exited = previous_support - current_support
                row["entered_state_count"] = len(entered)
                row["exited_state_count"] = len(exited)
                row["state_turnover_observed"] = bool(entered or exited)
                state_entries.append(float(len(entered)))
                state_exits.append(float(len(exited)))
                if current_support == previous_support and previous_target is not None:
                    row["target_movement_kl"] = _kl(current_target, previous_target)
                    if previous_log_potential is None:
                        raise AssertionError("real refinement lost previous potential")
                    potential_drift = _projective_potential_drift(
                        current_log_potential,
                        previous_log_potential,
                    )
                    row["potential_drift"] = potential_drift
                    row["stabilization_score"] = (
                        _as_float(row["kl_shift"])
                        + config.utility_delta_weight
                        * _as_float(row["absolute_utility_delta"])
                        + config.potential_drift_weight * potential_drift
                    )
                    stable = bool(
                        _as_float(row["stabilization_score"])
                        < config.stabilization_score_threshold
                    )
            cumulative_regret += _as_float(row["instantaneous_regret"])
            row["cumulative_regret"] = cumulative_regret
            streak = streak + 1 if stable else 0
            if streak >= config.consecutive_stable_rounds:
                reached = True
            previous_support = current_support
            previous_target = current_target
            previous_log_potential = current_log_potential
        stabilized += int(reached)
        final_kls.append(sequence[-1].update.kl_to_history)
        final_row = row_by_round_id[sequence[-1].round_id]
        final_tracking_errors.append(_as_float(final_row["tracking_error"]))
        cumulative_regrets.append(cumulative_regret)
    if not complete:
        blockers.append("no_complete_real_refinement_sequence")
    objective_gains = [_as_float(row["variational_objective_gain"]) for row in rows]
    optimizer_kls = [_as_float(row["proximal_optimizer_kl"]) for row in rows]
    target_movements = [
        _as_float(row["target_movement_kl"])
        for row in rows
        if row["target_movement_kl"] is not None
    ]
    monotonic_count = sum(value >= -tolerance for value in objective_gains)
    objective_verified = bool(objective_gains) and (
        monotonic_count == len(objective_gains)
        and max(optimizer_kls, default=math.inf) <= tolerance
    )
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
        stabilization_eligible_sequence_count=eligible,
        stabilized_sequence_count=stabilized,
        mean_final_kl_shift=(statistics.fmean(final_kls) if final_kls else None),
        variational_transition_count=len(objective_gains),
        variational_monotonic_transition_count=monotonic_count,
        minimum_variational_objective_gain=(min(objective_gains) if objective_gains else None),
        maximum_proximal_optimizer_kl=(max(optimizer_kls) if optimizer_kls else None),
        variational_objective_verified=objective_verified,
        mean_final_tracking_error=(
            statistics.fmean(final_tracking_errors) if final_tracking_errors else None
        ),
        mean_cumulative_regret=(
            statistics.fmean(cumulative_regrets) if cumulative_regrets else None
        ),
        mean_target_movement_kl=(statistics.fmean(target_movements) if target_movements else None),
        mean_state_entries_per_transition=(
            statistics.fmean(state_entries) if state_entries else None
        ),
        mean_state_exits_per_transition=(statistics.fmean(state_exits) if state_exits else None),
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


def _aggregate(values: list[float]) -> AggregateMetric:
    return aggregate_metric(values)


def _projective_potential_drift(
    current_log_potential: Mapping[str, float],
    previous_log_potential: Mapping[str, float],
) -> float:
    if set(current_log_potential) != set(previous_log_potential):
        raise ValueError("potential drift requires identical state support")
    deltas = [
        current_log_potential[key] - previous_log_potential[key]
        for key in current_log_potential
    ]
    return max(deltas) - min(deltas)


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
    total = sum(values.values())
    if total <= 0 or any(value <= 0 for value in values.values()):
        raise ValueError("refinement weights must be strictly positive")
    return {key: values[key] / total for key in sorted(values)}


def _kl(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    if set(left) != set(right):
        raise ValueError("KL distributions have different support")
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
