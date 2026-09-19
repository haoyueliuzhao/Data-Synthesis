"""CPU projections and repeat/leave-one-positive-out analyses of saved gradients."""

# ruff: noqa: E501 -- explicit fixed-denominator statistical definitions
import math

import fixed_kernel_proxy_numeric_20260919 as numeric
import numpy as np
import torch
from fixed_kernel_proxy_inputs_20260919 import probability

from trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo import distribution


class Geometry:
    def __init__(self, keys, pi, prior, mu, controls):
        self.keys = keys
        self.pi, self.prior, self.mu, self.controls = pi, prior, mu, controls
        self.tasks = {}
        for index, (task, state) in enumerate(keys):
            self.tasks.setdefault(task, []).append((index, state))
        self.weights = np.array([probability(mu[t]) * probability(pi[t][z]) for t, z in keys])
        self.mass = np.array([probability(mu[t]) for t, _ in keys])
        self.noncontrol = np.array([t not in controls for t, _ in keys])

    def flatten(self, values):
        return np.array([probability(values[t][z]) for t, z in self.keys])

    def nested(self, values):
        return {t: {z: float(values[i]) for i, z in pairs} for t, pairs in self.tasks.items()}

    def centered(self, dots):
        out = np.array(dots, dtype=np.float64, copy=True)
        for task, rows in self.tasks.items():
            indices = [i for i, _ in rows]
            weights = np.array([probability(self.pi[task][z]) for _, z in rows])
            average = np.einsum("i,i...->...", weights, out[indices])
            out[indices] = probability(self.mu[task]) * (out[indices] - average)
        return out

    def TV(self, left, right):
        return float(np.sum(self.mass * np.abs(np.asarray(left) - np.asarray(right))) / 2)

    def compare_C(self, left, right):
        mask = self.noncontrol
        x, y = np.asarray(left)[mask] / self.mass[mask], np.asarray(right)[mask] / self.mass[mask]
        w = self.weights[mask]
        w = w / float(w.sum())
        norm_x, norm_y = math.sqrt(float(np.sum(w * x * x))), math.sqrt(float(np.sum(w * y * y)))
        error = math.sqrt(float(np.sum(w * (x - y) ** 2)))
        substantial = np.abs(y) >= max(float(np.max(np.abs(y))) * 0.01, 1e-30)
        return dict(
            relative_weighted_RMS=error / max(norm_y, 1e-8),
            weighted_cosine=float(np.sum(w * x * y) / (norm_x * norm_y))
            if norm_x and norm_y
            else None,
            reference_weighted_norm=norm_y,
            error_weighted_norm=error,
            sign_disagreements=int(np.count_nonzero(np.sign(x) != np.sign(y))),
            sign_disagreements_reference_above_one_percent_max=int(
                np.count_nonzero((np.sign(x) != np.sign(y)) & substantial)
            ),
        )

    def propose(self, C, condition, positive_count):
        if positive_count == 0:
            return self.flatten(self.pi), "UNINFORMATIVE_ZERO_HALF"
        update = distribution.anchored_update(
            self.pi,
            self.prior,
            self.nested(C),
            self.mu,
            control_tasks=self.controls,
            contribution_only=condition == "c_only_anchored",
        )
        return self.flatten(update["pi_next"]), "INFORMATIVE"


def project(matrix, covectors, keys, geometry=None, *, rows=8):
    """One CPU batched dot pass per set of covectors; no new GPU gradients."""
    covectors = covectors.double()
    if covectors.ndim == 1:
        covectors = covectors[:, None]
    dots = np.empty((len(keys), covectors.shape[1]), dtype=np.float64)
    for start in range(0, len(keys), rows):
        dots[start : start + rows] = matrix[start : start + rows].double().mm(covectors).numpy()
    return dots if geometry is None else geometry.centered(dots)


def numerical_effect(
    matrix,
    context,
    keys,
    pi,
    prior,
    mu,
    controls,
    condition,
    saved_C,
    saved_pi,
    reference_a,
    limits,
):
    geometry = Geometry(keys, pi, prior, mu, controls)
    projected = project(
        matrix, torch.stack((context["a"].double(), reference_a.double()), dim=1), keys, geometry
    )
    historical, stable = projected[:, 0], projected[:, 1]
    stored = geometry.flatten(saved_C)
    historical_check = geometry.compare_C(historical, stored)
    # This is the necessary linkage of recomputed classes to saved C, not a new resource gate.
    if historical_check["relative_weighted_RMS"] > 1e-5:
        raise ValueError("recomputed class projection does not reproduce stored C")
    change = geometry.compare_C(stable, stored)
    next_pi, _ = geometry.propose(stable, condition, positive_count=1)
    TV = geometry.TV(next_pi, geometry.flatten(saved_pi))
    return dict(
        passed=change["relative_weighted_RMS"] <= limits["relative_weighted_C_RMS"]
        and TV <= limits["weighted_pi_TV"],
        historical_projection_check=historical_check,
        stable_vs_saved_C=change,
        stable_vs_saved_next_pi_weighted_TV=TV,
    ), geometry


def repeat_analysis(projected_items, positives, geometry, condition):
    """Each column is one unscaled positive trajectory's C; zero terms stay in n."""
    old_pi = geometry.flatten(geometry.pi)
    full_C = projected_items.sum(axis=1) / 360
    full_pi, full_status = geometry.propose(full_C, condition, len(positives))
    halves, proposals, half_rows = {}, {}, {}
    for repeat in (1, 2):
        selected = [i for i, row in enumerate(positives) if row["repeat"] == repeat]
        halves[repeat] = projected_items[:, selected].sum(axis=1) / 180
        proposals[repeat], status = geometry.propose(halves[repeat], condition, len(selected))
        half_rows[repeat] = dict(
            positive=len(selected),
            denominator=180,
            status=status,
            self_score=float(np.dot(halves[repeat], proposals[repeat] - old_pi)),
            weighted_pi_change=geometry.TV(proposals[repeat], old_pi),
        )
    both = all(half_rows[r]["positive"] for r in (1, 2))
    cross = dict(
        S_1_to_2=float(np.dot(halves[2], proposals[1] - old_pi)) if both else None,
        S_2_to_1=float(np.dot(halves[1], proposals[2] - old_pi)) if both else None,
        interpretable=bool(both),
        one_or_both_halves_zero_not_regrouped=not both,
    )
    loo = []
    for i, row in enumerate(positives):
        reduced = full_C - projected_items[:, i] / 360
        proposal, status = geometry.propose(reduced, condition, len(positives) - 1)
        compare = geometry.compare_C(reduced, full_C)
        repeat, other = row["repeat"], 3 - row["repeat"]
        half_reduced = halves[repeat] - projected_items[:, i] / 180
        half_proposal, half_status = geometry.propose(
            half_reduced, condition, half_rows[repeat]["positive"] - 1
        )
        loo.append(
            dict(
                index=row["index"],
                task_id=row["task_id"],
                source_cluster=row["source_cluster"],
                repeat=repeat,
                full_denominator=360,
                status=status,
                full_C_weighted_cosine=compare["weighted_cosine"],
                full_relative_C_change=compare["relative_weighted_RMS"],
                full_pi_change_TV=geometry.TV(proposal, full_pi),
                reduced_half_status=half_status,
                held_out_cross_score=float(np.dot(halves[other], half_proposal - old_pi))
                if half_status == "INFORMATIVE" and half_rows[other]["positive"]
                else None,
            )
        )
    cosines = [r["full_C_weighted_cosine"] for r in loo if r["full_C_weighted_cosine"] is not None]
    return dict(
        fixed_total_denominator=360,
        fixed_repeat_denominator=180,
        halves=half_rows,
        cross=cross,
        half_C_comparison=geometry.compare_C(halves[1], halves[2]),
        full_status=full_status,
        full_self_score=float(np.dot(full_C, full_pi - old_pi)),
        full_weighted_pi_change=geometry.TV(full_pi, old_pi),
        leave_one_out_summary=dict(
            positive_terms=len(loo),
            min_full_C_cosine=min(cosines) if cosines else None,
            max_relative_C_change=max((r["full_relative_C_change"] for r in loo), default=0),
            max_pi_TV_change=max((r["full_pi_change_TV"] for r in loo), default=0),
        ),
        leave_one_positive_out=loo,
        self_score_is_not_cross_validity=True,
        independent_task_generalization=False,
    )


def item_covectors(context, gradients, blocks, groups, clip):
    # At a fixed point the pullback is linear in the covector. Each trajectory
    # is evaluated once on CPU, and its resulting state projection is reused.
    result = torch.empty((context["G"].numel(), gradients.shape[0]), dtype=torch.float64)
    for index in range(gradients.shape[0]):
        value, _ = numeric.pullback(
            context["G"],
            context["first_moment"],
            context["second_moment"],
            -gradients[index],
            blocks,
            groups,
            clip,
        )
        result[:, index] = value
    return result
