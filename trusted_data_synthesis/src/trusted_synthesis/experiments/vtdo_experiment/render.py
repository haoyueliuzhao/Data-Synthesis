from __future__ import annotations

import csv
import html
import statistics
from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path

from .multistate import FinanceMultiStateReport
from .schema import (
    ContributionValidationReport,
    RefinementDynamicsReport,
    SyntheticExperimentReport,
    TrainingExperimentPreflight,
)

_COLORS = {
    "random": "#8c8c8c",
    "novelty_only": "#2f7ed8",
    "contribution_only": "#d95f02",
    "no_anchor": "#7570b3",
    "ccgr": "#1b9e77",
    "full_vtdo": "#c51b7d",
    "no_iteration": "#e6ab02",
    "no_quotient": "#666666",
}


def write_synthetic_table(report: SyntheticExperimentReport, path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(
            (
                "method",
                "run_count",
                "kl_to_vtdo_optimum_mean",
                "kl_ci95",
                "joint_utility_mean",
                "joint_utility_ci95",
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
                    item.final_kl_to_vtdo_optimum.mean,
                    item.final_kl_to_vtdo_optimum.ci95_half_width,
                    item.final_expected_utility.mean,
                    item.final_expected_utility.ci95_half_width,
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
                "expected_utility_mean",
                "expected_utility_ci95",
                "absolute_utility_delta_mean",
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
                    item.expected_utility.mean,
                    item.expected_utility.ci95_half_width,
                    (item.absolute_utility_delta.mean if item.absolute_utility_delta else None),
                    item.stabilization_score.mean if item.stabilization_score else None,
                    item.entropy.mean,
                    item.coverage_count.mean,
                    item.stable_seed_count,
                )
            )


def write_refinement_checkpoint_table(report: RefinementDynamicsReport, path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(
            (
                "round_index",
                "role",
                "expected_utility_mean",
                "expected_utility_ci95",
                "utility_gain_from_one_shot",
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
                    item.expected_utility.mean,
                    item.expected_utility.ci95_half_width,
                    item.utility_gain_from_one_shot,
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
            point.expected_contribution_novelty
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
        title="Synthetic VTDO: joint contribution-novelty utility",
        x_label="Refinement round",
        y_label="E[C x N]",
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
            report.practical_convergence.stabilization_score_threshold,
        ),
        (
            "Joint utility",
            "E[C_t x N_t]",
            [(item.round_index, item.expected_utility.mean) for item in report.round_aggregates],
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
        "Moving-potential VTDO refinement dynamics</text>"
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
    training: TrainingExperimentPreflight | None,
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
        "- Strict convergence is claimed only for the fixed-potential control.",
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
        "| Method | KL(pi_T || p*) | E[C x N] | Coverage alignment | Entropy |",
        "|---|---:|---:|---:|---:|",
    ]
    for item in synthetic.main_method_summaries:
        lines.append(
            f"| `{item.method}` | {item.final_kl_to_vtdo_optimum.mean:.4f} | "
            f"{item.final_expected_utility.mean:.4f} | "
            f"{item.final_coverage_alignment.mean:.4f} | {item.final_entropy.mean:.4f} |"
        )
    lines.extend(
        [
            "",
            "### Ablations",
            "",
            "| Ablation | KL(pi_T || p*) | E[C x N] | Coverage alignment | Entropy |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for item in synthetic.ablation_summaries:
        lines.append(
            f"| `{item.method}` | {item.final_kl_to_vtdo_optimum.mean:.4f} | "
            f"{item.final_expected_utility.mean:.4f} | "
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
        spearman = contribution.spearman_correlation
        sign_agreement = contribution.sign_agreement_rate
        lines.extend(
            [
                f"- Status: `{contribution.status}`",
                f"- Observations: {contribution.observation_count}",
                f"- Unique tasks: {contribution.unique_task_count}",
                f"- Spearman(C_hat, delta J): {spearman if spearman is not None else 'n/a'}",
                f"- Sign agreement: {sign_agreement if sign_agreement is not None else 'n/a'}",
            ]
        )

    convergence = refinement.practical_convergence
    lines.extend(
        [
            "",
            "## Refinement Dynamics",
            "",
            f"- Fixed-potential contraction verified: "
            f"`{refinement.fixed_potential_contraction.projective_contraction_verified}`",
            f"- Moving-potential horizon: {refinement.analysis_rounds} rounds",
            f"- Practical stabilization score: "
            f"`KL(pi_(t+1)||pi_t) + {convergence.utility_delta_weight:g} * "
            f"|U_(t+1)-U_t| < {convergence.stabilization_score_threshold:g}` for "
            f"{convergence.consecutive_rounds} consecutive rounds",
            f"- Controlled seeds satisfying criterion: {convergence.converged_seed_count}/"
            f"{convergence.evaluated_seed_count}",
            f"- Real financial round status: `{refinement.real_refinement.status}`",
            f"- Strict moving-potential convergence claim: "
            f"`{refinement.strict_convergence_claim_supported}`",
            "",
            "| Round | KL shift | Joint utility | |delta U| | Stabilization score "
            "| Entropy | Coverage |",
            "|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for item in refinement.round_aggregates:
        lines.append(
            f"| {item.round_index} | "
            f"{item.kl_shift.mean if item.kl_shift else 'n/a'} | "
            f"{item.expected_utility.mean:.4f} | "
            f"{item.absolute_utility_delta.mean if item.absolute_utility_delta else 'n/a'} | "
            f"{item.stabilization_score.mean if item.stabilization_score else 'n/a'} | "
            f"{item.entropy.mean:.4f} | {item.coverage_count.mean:.1f} |"
        )

    lines.extend(["", "## Equal-budget B1-B5 Training Gate", ""])
    if training is None:
        lines.append("Not configured.")
    else:
        lines.extend(
            [
                f"- Student: `{training.base_model}`",
                f"- Supervised tokens per arm: {training.supervised_token_budget:,}",
                f"- Formal training ready: `{training.formal_training_ready}`",
                f"- Benchmark snapshots: `{training.external_benchmark_status}`",
                "",
                "| Arm | Records | Tasks | States | Multi-state tasks | Status |",
                "|---|---:|---:|---:|---:|---|",
            ]
        )
        for item in training.arms:
            lines.append(
                f"| `{item.arm_id}` | {item.source_record_count} | "
                f"{item.unique_task_count} | {item.unique_state_count} | "
                f"{item.multi_state_task_count} | `{item.capacity_status}` |"
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
        color = _COLORS[method]
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
