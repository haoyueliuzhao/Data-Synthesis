from __future__ import annotations

import csv
import html
import statistics
from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path

from .multistate import FinanceMultiStateReport
from .schema import (
    BeneficiaryStateShiftReport,
    ContributionValidationReport,
    RefinementCheckpointTrainingPreflight,
    RefinementDynamicsReport,
    SyntheticExperimentReport,
    TrainingExperimentPreflight,
)

_COLORS = {
    "no_feedback": "#8c8c8c",
    "static_optimization": "#2f7ed8",
    "random": "#8c8c8c",
    "novelty_only": "#2f7ed8",
    "contribution_only": "#d95f02",
    "no_global_coverage_anchor": "#7570b3",
    "no_coverage_prior": "#a6761d",
    "ccgr": "#1b9e77",
    "full_vtdo": "#c51b7d",
    "no_iteration": "#e6ab02",
    "no_quotient_exact": "#666666",
    "no_quotient_noisy": "#b3b3b3",
}


def _format_optional_float(value: float | None, format_spec: str = ".6g") -> str:
    return format(value, format_spec) if value is not None else "n/a"


def write_synthetic_table(report: SyntheticExperimentReport, path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(
            (
                "method",
                "run_count",
                "expected_log_potential_mean",
                "expected_log_potential_ci95",
                "anchored_variational_objective_mean",
                "anchored_variational_objective_ci95",
                "contribution_novelty_diagnostic_mean",
                "coverage_alignment_mean",
                "coverage_alignment_ci95",
                "entropy_mean",
                "entropy_ci95",
                "top_right_mass_mean",
            )
        )
        for item in (*report.main_method_summaries, *report.ablation_summaries):
            writer.writerow(
                (
                    item.method,
                    item.run_count,
                    item.final_expected_log_potential.mean,
                    item.final_expected_log_potential.ci95_half_width,
                    item.final_anchored_variational_objective.mean,
                    item.final_anchored_variational_objective.ci95_half_width,
                    item.final_expected_contribution_novelty_diagnostic.mean,
                    item.final_coverage_alignment.mean,
                    item.final_coverage_alignment.ci95_half_width,
                    item.final_entropy.mean,
                    item.final_entropy.ci95_half_width,
                    item.final_top_right_mass.mean,
                )
            )


def write_refinement_round_table(report: RefinementDynamicsReport, path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(
            (
                "round_index",
                "transition_from_round",
                "kl_shift_mean",
                "kl_shift_ci95",
                "expected_log_potential_mean",
                "expected_log_potential_ci95",
                "absolute_utility_delta_mean",
                "potential_drift_mean",
                "stabilization_score_mean",
                "entropy_mean",
                "coverage_count_mean",
                "stable_seed_count",
            )
        )
        for item in report.round_aggregates:
            writer.writerow(
                (
                    item.round_index,
                    item.transition_from_round,
                    item.kl_shift.mean if item.kl_shift else None,
                    item.kl_shift.ci95_half_width if item.kl_shift else None,
                    item.expected_log_potential.mean,
                    item.expected_log_potential.ci95_half_width,
                    (item.absolute_utility_delta.mean if item.absolute_utility_delta else None),
                    item.potential_drift.mean if item.potential_drift else None,
                    item.stabilization_score.mean if item.stabilization_score else None,
                    item.entropy.mean,
                    item.coverage_count.mean,
                    item.stable_seed_count,
                )
            )


def write_moving_potential_table(report: RefinementDynamicsReport, path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(
            (
                "track",
                "is_primary_track",
                "method",
                "run_count",
                "mean_tracking_error",
                "mean_tracking_error_ci95",
                "final_tracking_error",
                "cumulative_regret",
                "final_anchor_objective",
            )
        )
        for moving in report.moving_potential_tracks:
            for item in moving.method_summaries:
                writer.writerow(
                    (
                        moving.track,
                        moving.is_primary_track,
                        item.method,
                        item.run_count,
                        item.mean_tracking_error.mean,
                        item.mean_tracking_error.ci95_half_width,
                        item.final_tracking_error.mean,
                        item.cumulative_regret.mean,
                        item.final_anchor_objective.mean,
                    )
                )


def write_refinement_checkpoint_table(report: RefinementDynamicsReport, path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(
            (
                "round_index",
                "role",
                "expected_log_potential_mean",
                "expected_log_potential_ci95",
                "log_potential_difference_from_round_one",
                "kl_shift_mean",
                "entropy_mean",
                "coverage_count_mean",
                "downstream_training_evaluated",
            )
        )
        for item in report.checkpoint_summaries:
            writer.writerow(
                (
                    item.round_index,
                    item.role,
                    item.expected_log_potential.mean,
                    item.expected_log_potential.ci95_half_width,
                    item.log_potential_difference_from_round_one,
                    item.kl_shift.mean,
                    item.entropy.mean,
                    item.coverage_count.mean,
                    item.downstream_training_evaluated,
                )
            )


def write_distribution_figure(report: SyntheticExperimentReport, path: Path) -> None:
    by_method_round: defaultdict[tuple[str, int], list[float]] = defaultdict(list)
    for point in report.metric_points:
        by_method_round[(point.method, point.round_index)].append(
            point.anchored_variational_objective
        )
    series = {
        method: [
            (
                round_index,
                statistics.fmean(by_method_round[(method, round_index)]),
            )
            for round_index in sorted(key[1] for key in by_method_round if key[0] == method)
        ]
        for method in _COLORS
    }
    _line_svg(
        path,
        series,
        title="Synthetic VTDO: anchored variational objective",
        x_label="Refinement round",
        y_label="F(pi; pi_previous, r, Phi)",
    )


def write_phase_figure(
    phase_rows: Iterable[Mapping[str, float | int | str]],
    path: Path,
) -> None:
    rows = tuple(phase_rows)
    width, height = 980, 620
    left, top, right, bottom = 85, 55, 35, 75
    plot_w = width - left - right
    plot_h = height - top - bottom
    x_values = [float(row["normalized_novelty"]) for row in rows]
    y_values = [float(row["normalized_contribution"]) for row in rows]
    d_values = [float(row["probability_delta"]) for row in rows]
    x_min, x_max = _extent(x_values)
    y_min, y_max = _extent(y_values)
    delta_max = max((abs(value) for value in d_values), default=1.0) or 1.0
    elements = [_svg_header(width, height)]
    elements.append(
        f'<text x="{width / 2}" y="28" text-anchor="middle" '
        'font-size="18" font-family="sans-serif">'
        "AEVTDR contribution-novelty phase observations</text>"
    )
    elements.extend(
        _axes(
            left,
            top,
            plot_w,
            plot_h,
            "Normalized novelty",
            "Normalized contribution",
        )
    )
    for row in rows:
        x = left + (float(row["normalized_novelty"]) - x_min) / (x_max - x_min) * plot_w
        y = (
            top
            + plot_h
            - ((float(row["normalized_contribution"]) - y_min) / (y_max - y_min) * plot_h)
        )
        delta = float(row["probability_delta"])
        color = "#b2182b" if delta >= 0 else "#2166ac"
        opacity = 0.12 + 0.7 * min(abs(delta) / delta_max, 1.0)
        elements.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2.4" fill="{color}" '
            f'fill-opacity="{opacity:.3f}" />'
        )
    elements.append(
        f'<text x="{left}" y="{height - 18}" font-size="12" font-family="sans-serif">'
        "Red: probability increased; blue: probability decreased.</text>"
    )
    elements.append("</svg>")
    path.write_text("\n".join(elements) + "\n", encoding="utf-8")


def write_moving_potential_figure(
    rows: Iterable[Mapping[str, object]],
    path: Path,
) -> None:
    grouped: defaultdict[tuple[str, str, int], list[float]] = defaultdict(list)
    for row in rows:
        grouped[
            (
                str(row["track"]),
                str(row["method"]),
                _integer(row["round_index"]),
            )
        ].append(_number(row["tracking_error"]))
    series = {
        f"{track}/{method}": [
            (round_index, statistics.fmean(grouped[(track, method, round_index)]))
            for round_index in sorted(
                key[2] for key in grouped if key[0] == track and key[1] == method
            )
        ]
        for track in sorted({key[0] for key in grouped})
        for method in ("no_feedback", "static_optimization", "full_vtdo")
    }
    _line_svg(
        path,
        series,
        title="Moving-potential benchmark: instantaneous-optimum tracking",
        x_label="Refinement round",
        y_label="KL(policy || instantaneous optimum)",
    )


def write_refinement_dynamics_figure(
    report: RefinementDynamicsReport,
    path: Path,
) -> None:
    panels = (
        (
            "Practical stabilization",
            "KL + lambda * |delta U|",
            [
                (item.round_index, item.stabilization_score.mean)
                for item in report.round_aggregates
                if item.stabilization_score is not None
            ],
            report.practical_stabilization.stabilization_score_threshold,
        ),
        (
            "Current-potential utility",
            "E_pi[log Phi_t]",
            [
                (item.round_index, item.expected_log_potential.mean)
                for item in report.round_aggregates
            ],
            None,
        ),
        (
            "Distribution entropy",
            "H(pi_t)",
            [(item.round_index, item.entropy.mean) for item in report.round_aggregates],
            None,
        ),
        (
            "Active state coverage",
            "|{z: pi_t(z) > epsilon}|",
            [(item.round_index, item.coverage_count.mean) for item in report.round_aggregates],
            None,
        ),
    )
    width, height = 1100, 760
    panel_w, panel_h = 475, 275
    origins = ((75, 75), (610, 75), (75, 430), (610, 430))
    elements = [_svg_header(width, height)]
    elements.append(
        f'<text x="{width / 2}" y="30" text-anchor="middle" '
        'font-size="19" font-family="sans-serif">'
        "Finite-step VTDO stabilization diagnostics</text>"
    )
    for (title, y_label, points, threshold), (left, top) in zip(panels, origins, strict=True):
        x_min, x_max = _extent([float(item[0]) for item in points])
        y_values = [item[1] for item in points]
        if threshold is not None:
            y_values.append(threshold)
        y_min, y_max = _extent(y_values)
        elements.append(
            f'<text x="{left + panel_w / 2}" y="{top - 17}" text-anchor="middle" '
            f'font-size="15" font-family="sans-serif">{html.escape(title)}</text>'
        )
        elements.extend(_axes(left, top, panel_w, panel_h, "Round", y_label))
        coordinates = []
        for x_value, y_value in points:
            x = left + (x_value - x_min) / (x_max - x_min) * panel_w
            y = top + panel_h - (y_value - y_min) / (y_max - y_min) * panel_h
            coordinates.append(f"{x:.2f},{y:.2f}")
            elements.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3" fill="#c51b7d" />')
        elements.append(
            f'<polyline points="{" ".join(coordinates)}" fill="none" '
            'stroke="#c51b7d" stroke-width="2.5" />'
        )
        if threshold is not None:
            y = top + panel_h - (threshold - y_min) / (y_max - y_min) * panel_h
            elements.append(
                f'<line x1="{left}" y1="{y:.2f}" x2="{left + panel_w}" '
                f'y2="{y:.2f}" stroke="#444444" stroke-dasharray="6,5" />'
            )
            elements.append(
                f'<text x="{left + 6}" y="{y - 6:.2f}" font-size="11" '
                f'font-family="sans-serif">threshold={threshold:g}</text>'
            )
    elements.append("</svg>")
    path.write_text("\n".join(elements) + "\n", encoding="utf-8")


def write_markdown_report(
    path: Path,
    *,
    synthetic: SyntheticExperimentReport,
    refinement: RefinementDynamicsReport,
    multi_state: FinanceMultiStateReport | None,
    contribution: ContributionValidationReport | None,
    beneficiary_shift: BeneficiaryStateShiftReport | None,
    training: TrainingExperimentPreflight | None,
    checkpoint_training: RefinementCheckpointTrainingPreflight | None,
    limitations: tuple[str, ...],
) -> None:
    lines = [
        "# VTDO Experiment Report",
        "",
        "## Frozen Method Boundary",
        "",
        f"- Production algorithm: `{synthetic.production_algorithm_id}` / "
        f"`{synthetic.production_algorithm_version}`",
        "- Paper logic: `Trajectory State -> Distribution Refinement -> Equal-budget Training`.",
        "- Validity is a feasibility gate; only independently accepted quotient states may "
        "enter positive-support arms.",
        "- Fixed-potential analysis verifies the update operator; it is not a claim about "
        "closed-loop convergence.",
        "",
        "## Controlled VTDO Validation",
        "",
        f"- State count K: {synthetic.state_count}",
        f"- Seed count: {len(synthetic.accepted_state_counts)}",
        "- Initial accepted-state contribution has zero expectation under pi_0.",
        "- Main baselines and ablations are reported separately.",
        "",
        "### Main methods",
        "",
        "| Method | E[log Phi] | Anchored objective | C x N diagnostic | "
        "Coverage alignment | Entropy |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for item in synthetic.main_method_summaries:
        lines.append(
            f"| `{item.method}` | {item.final_expected_log_potential.mean:.4f} | "
            f"{item.final_anchored_variational_objective.mean:.4f} | "
            f"{item.final_expected_contribution_novelty_diagnostic.mean:.4f} | "
            f"{item.final_coverage_alignment.mean:.4f} | {item.final_entropy.mean:.4f} |"
        )
    lines.extend(
        [
            "",
            "### Ablations",
            "",
            "| Ablation | E[log Phi] | Anchored objective | C x N diagnostic | "
            "Coverage alignment | Entropy |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for item in synthetic.ablation_summaries:
        lines.append(
            f"| `{item.method}` | {item.final_expected_log_potential.mean:.4f} | "
            f"{item.final_anchored_variational_objective.mean:.4f} | "
            f"{item.final_expected_contribution_novelty_diagnostic.mean:.4f} | "
            f"{item.final_coverage_alignment.mean:.4f} | {item.final_entropy.mean:.4f} |"
        )

    lines.extend(["", "## Real Financial Trajectory States", ""])
    if multi_state is None:
        lines.append("Not configured.")
    else:
        lines.extend(
            [
                f"- Status: `{multi_state.status}`",
                f"- Accepted task quota: {multi_state.accepted_task_count}/"
                f"{multi_state.requested_task_count}",
                f"- Attempted tasks: {multi_state.attempted_task_count} "
                f"(rejected: {multi_state.rejected_task_count})",
                f"- Accepted states: {multi_state.accepted_trajectory_count}",
                f"- States per task: {multi_state.minimum_states_observed}-"
                f"{multi_state.maximum_states_observed}",
                f"- Strategy verifier passes: "
                f"{multi_state.strategy_verifier_pass_count}/"
                f"{multi_state.strategy_attempt_count} "
                f"({multi_state.independent_verifier_pass_rate:.2%})",
                f"- Strategy verifier failures: {multi_state.strategy_verifier_failure_count}",
                f"- Duplicate quotient states removed: {multi_state.duplicate_state_count}",
                f"- Adversarial mutations rejected: "
                f"{multi_state.adversarial_mutation_rejection_count}",
                f"- Surface-probe quotient merge rate: {multi_state.quotient_merge_rate:.2%}",
                "- Program-DAG diversity is not claimed; accepted states differ through "
                "retrieval breadth, verification frontier, and evidence lineage.",
            ]
        )

    lines.extend(["", "## Empirical Contribution Validation", ""])
    if contribution is None:
        lines.append("Not configured.")
    else:
        sign_agreement = contribution.sign_agreement_rate
        task_rank = contribution.task_rank_correlation
        centered = contribution.centered_global_spearman
        concordance = contribution.pairwise_concordance_rate
        lines.extend(
            [
                f"- Status: `{contribution.status}`",
                f"- Observations: {contribution.observation_count}",
                f"- Paired Probe/Intervention seeds per state: {contribution.paired_seed_count}",
                f"- Aggregated task-state cells: {contribution.aggregated_state_count}",
                f"- Mean within-state Intervention variance: "
                f"{_format_optional_float(contribution.mean_within_state_intervention_variance)}",
                f"- Unique tasks/rounds: {contribution.unique_task_count}/"
                f"{contribution.unique_round_count}",
                f"- Eligible task-round cells: "
                f"{contribution.eligible_task_round_count}/"
                f"{contribution.unique_task_round_count}",
                f"- Macro within-task Spearman: {task_rank.mean if task_rank else 'n/a'}",
                f"- Centered global Spearman: {centered if centered is not None else 'n/a'}",
                f"- Pairwise concordance: {concordance if concordance is not None else 'n/a'}",
                f"- Sign agreement: {sign_agreement if sign_agreement is not None else 'n/a'}",
            ]
        )

    lines.extend(["", "## Beneficiary Model-State Shift", ""])
    if beneficiary_shift is None:
        lines.append("Not configured.")
    else:
        mean_shift = beneficiary_shift.mean_absolute_contribution_shift
        task_rank = beneficiary_shift.task_rank_correlation
        lines.extend(
            [
                f"- Status: `{beneficiary_shift.status}`",
                f"- Baseline model state: `{beneficiary_shift.baseline_model_state_id}`",
                f"- Updated model state: `{beneficiary_shift.updated_model_state_id}`",
                f"- Compared rounds: {beneficiary_shift.baseline_round_index} -> "
                f"{beneficiary_shift.updated_round_index}",
                f"- Atomic paired interventions: {beneficiary_shift.atomic_pair_count}",
                f"- Aggregated task-state cells: {beneficiary_shift.aggregated_state_count}",
                f"- Mean absolute Contribution shift: {mean_shift.mean if mean_shift else 'n/a'}",
                f"- Mean-shift CI lower bound: "
                f"{beneficiary_shift.mean_absolute_shift_ci95_lower_bound}",
                f"- Task-wise C0/C1 rank correlation: {task_rank.mean if task_rank else 'n/a'}",
                f"- Contribution direction-change rate: "
                f"{beneficiary_shift.contribution_direction_change_rate}",
                f"- Model-state dependence observed above tolerance: "
                f"`{beneficiary_shift.model_state_dependence_observed}`",
            ]
        )

    stabilization = refinement.practical_stabilization
    moving_tracks = refinement.moving_potential_tracks
    moving = next(item for item in moving_tracks if item.is_primary_track)
    objective = moving.variational_objective
    lines.extend(
        [
            "",
            "## Refinement Dynamics",
            "",
            f"- Fixed-potential update operator verified: "
            f"`{refinement.fixed_potential_contraction.projective_contraction_verified}`",
            f"- Primary moving-potential track: `{moving.track}`",
            f"- Primary moving-potential tracking status: `{moving.status}`",
            f"- Potential sequence contract: {moving.potential_sequence_definition}",
            f"- Variational objective monotonic transitions: "
            f"{objective.monotonic_transition_count}/{objective.transition_count}",
            f"- Minimum variational objective gain: {objective.minimum_objective_gain:.6g}",
            f"- Maximum KL to the exact proximal optimizer: "
            f"{objective.maximum_proximal_optimizer_kl:.6g}",
            f"- VTDO cumulative-regret advantage over no-feedback (primary track): "
            f"{moving.vtdo_regret_advantage_over_no_feedback.mean:.4f} "
            f"+/- {moving.vtdo_regret_advantage_over_no_feedback.ci95_half_width:.4f}",
            f"- VTDO cumulative-regret advantage over static one-shot (primary track): "
            f"{moving.vtdo_regret_advantage_over_static.mean:.4f} "
            f"+/- {moving.vtdo_regret_advantage_over_static.ci95_half_width:.4f}",
            f"- Finite-step stabilization horizon: {refinement.analysis_rounds} rounds",
            f"- Practical stabilization score: "
            f"`KL(pi_(t+1)||pi_t) + {stabilization.utility_delta_weight:g} * "
            f"|E_pi_(t+1)[log Phi_t]-E_pi_t[log Phi_t]| + "
            f"{stabilization.potential_drift_weight:g} * D_Phi(t) "
            f"< {stabilization.stabilization_score_threshold:g}` for "
            f"{stabilization.consecutive_rounds} consecutive rounds",
            f"- Controlled seeds satisfying criterion: {stabilization.stabilized_seed_count}/"
            f"{stabilization.evaluated_seed_count}",
            f"- Real financial round status: `{refinement.real_refinement.status}`",
            f"- Strict moving-potential convergence claim: "
            f"`{refinement.strict_convergence_claim_supported}`",
            "",
            "### Moving-optimum benchmark",
            "",
            "| Track | Role | Method | Mean tracking KL | Final tracking KL | Cumulative regret |",
            "|---|---|---|---:|---:|---:|",
        ]
    )
    for track in moving_tracks:
        for item in track.method_summaries:
            lines.append(
                f"| `{track.track}` | "
                f"{'primary' if track.is_primary_track else 'diagnostic'} | "
                f"`{item.method}` | {item.mean_tracking_error.mean:.4f} | "
                f"{item.final_tracking_error.mean:.4f} | "
                f"{item.cumulative_regret.mean:.4f} |"
            )
    real = refinement.real_refinement
    if real.status != "not_configured":
        lines.extend(
            [
                "",
                "### Real feedback replay",
                "",
                f"- Variational transitions verified: "
                f"{real.variational_monotonic_transition_count}/"
                f"{real.variational_transition_count}",
                f"- Exact proximal replay: `{real.variational_objective_verified}`",
                f"- Stabilized sequences: {real.stabilized_sequence_count}/"
                f"{real.stabilization_eligible_sequence_count}",
                f"- Mean final tracking KL: {real.mean_final_tracking_error}",
                f"- Mean cumulative regret: {real.mean_cumulative_regret}",
                f"- Exact task set: expected={real.expected_task_condition_count}, "
                f"missing={real.missing_task_condition_count}, "
                f"unexpected={real.unexpected_task_condition_count}",
                f"- Turnover probability threshold: {real.turnover_probability_threshold}",
                f"- Mean state entries/exits per transition: "
                f"{real.mean_state_entries_per_transition}/"
                f"{real.mean_state_exits_per_transition}",
            ]
        )
    lines.extend(
        [
            "",
            "### Finite-step stabilization",
            "",
            "| Round | KL shift | E[log Phi_t] | abs(delta U) | Potential drift "
            "| Stabilization score | Entropy | Coverage |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for item in refinement.round_aggregates:
        lines.append(
            f"| {item.round_index} | "
            f"{item.kl_shift.mean if item.kl_shift else 'n/a'} | "
            f"{item.expected_log_potential.mean:.4f} | "
            f"{item.absolute_utility_delta.mean if item.absolute_utility_delta else 'n/a'} | "
            f"{item.potential_drift.mean if item.potential_drift else 'n/a'} | "
            f"{item.stabilization_score.mean if item.stabilization_score else 'n/a'} | "
            f"{item.entropy.mean:.4f} | {item.coverage_count.mean:.1f} |"
        )

    lines.extend(["", "## Equal-supervised-token Training Arm Gate", ""])
    if training is None:
        lines.append("Not configured.")
    else:
        lines.extend(
            [
                f"- Student: `{training.base_model}`",
                f"- Supervised tokens per arm: {training.supervised_token_budget:,}",
                f"- Primary causal training ready: `{training.primary_causal_training_ready}`",
                f"- Full comparison matrix ready: `{training.full_comparison_matrix_ready}`",
                f"- Explicitly permitted arms: {', '.join(training.permitted_arm_ids) or 'none'}",
                f"- Primary fixed task-marginal contract: "
                f"`{training.primary_task_marginal_contract_verified}`",
                f"- Benchmark snapshots: `{training.external_benchmark_status}`",
                "",
                "| Arm | Role | Records | Tasks | States | Multi-state tasks | "
                "Task marginal | Status |",
                "|---|---|---:|---:|---:|---:|---|---|",
            ]
        )
        for item in training.arms:
            lines.append(
                f"| `{item.arm_id}` | `{item.comparison_role}` | "
                f"{item.source_record_count} | "
                f"{item.unique_task_count} | {item.unique_state_count} | "
                f"{item.multi_state_task_count} | `{item.task_marginal_policy}` / "
                f"`{item.task_marginal_verified}` | `{item.capacity_status}` |"
            )

    lines.extend(["", "## One-shot vs Iterative Training Checkpoints", ""])
    if checkpoint_training is None:
        lines.append("Not configured.")
    else:
        lines.extend(
            [
                f"- Ready: `{checkpoint_training.ready}`",
                f"- Analysis checkpoints: {checkpoint_training.analysis_checkpoint_rounds}",
                f"- Training checkpoints: {checkpoint_training.training_checkpoint_rounds}",
                "- Materialized training rounds: "
                f"{checkpoint_training.materialized_training_rounds}",
                f"- Equal supervised-token budget: {checkpoint_training.supervised_token_budget:,}",
                f"- External benchmark status: `{checkpoint_training.external_benchmark_status}`",
            ]
        )
        if checkpoint_training.blockers:
            lines.append(
                "- Blockers: " + ", ".join(f"`{item}`" for item in checkpoint_training.blockers)
            )

    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {item}" for item in limitations)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _line_svg(
    path: Path,
    series: Mapping[str, list[tuple[int, float]]],
    *,
    title: str,
    x_label: str,
    y_label: str,
) -> None:
    width, height = 980, 620
    left, top, right, bottom = 85, 55, 190, 75
    plot_w = width - left - right
    plot_h = height - top - bottom
    points = [point for values in series.values() for point in values]
    x_min, x_max = _extent([float(item[0]) for item in points])
    y_min, y_max = _extent([item[1] for item in points])
    elements = [_svg_header(width, height)]
    elements.append(
        f'<text x="{width / 2}" y="28" text-anchor="middle" '
        f'font-size="18" font-family="sans-serif">{html.escape(title)}</text>'
    )
    elements.extend(_axes(left, top, plot_w, plot_h, x_label, y_label))
    legend_y = top + 10
    for method, values in series.items():
        if not values:
            continue
        coordinates = []
        for x_value, y_value in values:
            x = left + (x_value - x_min) / (x_max - x_min) * plot_w
            y = top + plot_h - (y_value - y_min) / (y_max - y_min) * plot_h
            coordinates.append(f"{x:.2f},{y:.2f}")
        color = _series_color(method)
        elements.append(
            f'<polyline points="{" ".join(coordinates)}" fill="none" '
            f'stroke="{color}" stroke-width="2" />'
        )
        elements.append(
            f'<line x1="{width - right + 25}" y1="{legend_y}" '
            f'x2="{width - right + 55}" y2="{legend_y}" stroke="{color}" stroke-width="3" />'
        )
        elements.append(
            f'<text x="{width - right + 62}" y="{legend_y + 4}" '
            f'font-size="12" font-family="sans-serif">{html.escape(method)}</text>'
        )
        legend_y += 25
    elements.append("</svg>")
    path.write_text("\n".join(elements) + "\n", encoding="utf-8")


def _axes(
    left: int,
    top: int,
    plot_w: int,
    plot_h: int,
    x_label: str,
    y_label: str,
) -> list[str]:
    return [
        f'<rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" '
        'fill="#ffffff" stroke="#444444" />',
        f'<text x="{left + plot_w / 2}" y="{top + plot_h + 48}" '
        f'text-anchor="middle" font-size="13" font-family="sans-serif">'
        f"{html.escape(x_label)}</text>",
        f'<text x="20" y="{top + plot_h / 2}" text-anchor="middle" '
        f'transform="rotate(-90 20 {top + plot_h / 2})" font-size="13" '
        f'font-family="sans-serif">{html.escape(y_label)}</text>',
    ]


def _svg_header(width: int, height: int) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
    )


def _extent(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 1.0
    minimum, maximum = min(values), max(values)
    if maximum == minimum:
        return minimum - 0.5, maximum + 0.5
    padding = (maximum - minimum) * 0.05
    return minimum - padding, maximum + padding


def _number(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    raise TypeError("render metric is not numeric")


def _integer(value: object) -> int:
    if isinstance(value, int):
        return value
    raise TypeError("render index is not an integer")


def _series_color(name: str) -> str:
    if name in _COLORS:
        return _COLORS[name]
    palette = (
        "#1b9e77",
        "#d95f02",
        "#7570b3",
        "#e7298a",
        "#66a61e",
        "#e6ab02",
        "#a6761d",
        "#1f78b4",
        "#b15928",
    )
    return palette[sum(name.encode("utf-8")) % len(palette)]
