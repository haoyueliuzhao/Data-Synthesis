"""Experiment 2 pure arithmetic, not evidence of observed training improvement.

Inputs C already contain the task marginal mu from the Adam-aware kernel. This
module never estimates C from correctness counts or adds another mu/pi factor.
The caller must first validate and seal genuine 350 x 2 feedback trajectories.
"""

from __future__ import annotations

import math
from fractions import Fraction

from .contracts import digest
from .v6_distribution import automatic_update


def _float(value):
    if isinstance(value, bool):
        raise ValueError("boolean is not a numeric contribution or probability")
    result = float(Fraction(value)) if isinstance(value, str) else float(value)
    if not math.isfinite(result):
        raise ValueError("finite numeric input required")
    return result


def _direction(old, new):
    return {t: {z: _float(new[t][z]) - _float(p) for z, p in row.items()} for t, row in old.items()}


def _dot(C, direction):
    return math.fsum(_float(C[t][z]) * d for t, row in direction.items() for z, d in row.items())


def distribution_change(current, updated, mu):
    if set(current) != set(updated) or set(current) != set(mu):
        raise ValueError("unchanged task population required")
    masses = {t: _float(v) for t, v in mu.items()}
    if min(masses.values(), default=0) <= 0 or not math.isclose(
        sum(masses.values()), 1, abs_tol=1e-12
    ):
        raise ValueError("positive normalized original task marginals required")
    tasks = {}
    for t, row in current.items():
        if not row or set(row) != set(updated[t]):
            raise ValueError("no missing/added states or clipping")
        p, q = {z: _float(v) for z, v in row.items()}, {z: _float(v) for z, v in updated[t].items()}
        if min(*p.values(), *q.values()) <= 0 or any(
            not math.isclose(sum(v.values()), 1, abs_tol=1e-12) for v in (p, q)
        ):
            raise ValueError("positive normalized full support required")
        tasks[t] = dict(
            TV=0.5 * math.fsum(abs(q[z] - p[z]) for z in p),
            KL_new_to_old=math.fsum(q[z] * math.log(q[z] / p[z]) for z in p),
            entropy_old=-math.fsum(v * math.log(v) for v in p.values()),
            entropy_new=-math.fsum(v * math.log(v) for v in q.values()),
        )
    return dict(
        per_task=tasks,
        mu_weighted={
            k: math.fsum(masses[t] * r[k] for t, r in tasks.items())
            for k in ("TV", "KL_new_to_old", "entropy_old", "entropy_new")
        },
    )


def cross_repeat_diagnostics(
    current, prior, C_by_repeat, mu, *, denominators, feedback_all_zero=(False, False)
):
    """One repeat proposes d; the OTHER repeat evaluates it, without extra samples.

    Metadata/number checks do not establish that a real feedback seal exists.
    Full training must use the complete 700-sample estimator, never the better half.
    """
    if tuple(denominators) != (350, 350) or len(C_by_repeat) != 2:
        raise ValueError("both repeat denominators must remain 350, including zero rewards")
    if len(feedback_all_zero) != 2 or any(type(v) is not bool for v in feedback_all_zero):
        raise ValueError("explicit all-zero flags for both complete repeats required")
    updates = [
        automatic_update(current, prior, C, mu, arm="C-only", feedback_all_zero=zero)
        for C, zero in zip(C_by_repeat, feedback_all_zero, strict=True)
    ]
    qs = [u["pi_next"] for u in updates]
    ds = [_direction(current, q) for q in qs]
    averaged = {
        t: {z: math.fsum(_float(C[t][z]) for C in C_by_repeat) / 2 for z in row}
        for t, row in current.items()
    }
    return dict(
        schema="v6_cross_repeat_arithmetic.v1",
        denominators=[350, 350],
        full_feedback_denominator=700,
        C_full_from_equal_halves=averaged,
        S_0_to_1=_dot(C_by_repeat[1], ds[0]),
        S_1_to_0=_dot(C_by_repeat[0], ds[1]),
        self_scores=[_dot(C_by_repeat[i], ds[i]) for i in (0, 1)],
        self_scores_are_not_independent_validation=True,
        proposed_pi=qs,
        distribution_changes=[distribution_change(current, q, mu) for q in qs],
        contribution_already_contains_mu=True,
        additional_mu_or_pi_factor=False,
        selected_repeat=None,
        actual_update_requires_complete_700=True,
        actual_feedback_provenance_verified=False,
        training_benefit_established=False,
    )


def same_point_n_diagnostics(current, prior, C, mu, *, feedback_all_zero=False):
    """Distribution-only N intervention, not a substitute for step800->1000 training."""
    c_only = automatic_update(
        current, prior, C, mu, arm="C-only", feedback_all_zero=feedback_all_zero
    )
    full = automatic_update(current, prior, C, mu, arm="Full", feedback_all_zero=feedback_all_zero)
    difference = distribution_change(c_only["pi_next"], full["pi_next"], mu)
    return dict(
        schema="v6_same_point_N_arithmetic.v1",
        inputs_sha256=digest(
            dict(current=current, prior=prior, C=C, mu=mu, feedback_all_zero=feedback_all_zero)
        ),
        C_only=c_only["pi_next"],
        Full=full["pi_next"],
        difference=difference,
        N_distribution_effect_nonzero=difference["mu_weighted"]["TV"] > 1e-12,
        genuine_theta_Adam_RNG_G_feedback_identity_verified=False,
        local_training_effect=None,
        closed_loop_effect=None,
    )


def direction_utility_report(rows, *, registered_keys):
    """Fixed 120 x (2 sampled + 1 greedy) comparisons at one seed's step600.

    'Less harmed than reverse' is distinguished from positive-vs-Static benefit.
    Raw scores are arithmetic inputs, never asserted here to be actual model runs.
    """
    expected = tuple(registered_keys)
    if len(expected) != 360 or len(set(expected)) != 360:
        raise ValueError("fixed 360 distinct calibration coordinates required per seed")
    if set(rows) != {"Static", "positive", "reverse"}:
        raise ValueError("all three registered directions must be reported")
    means = {}
    for arm, values in rows.items():
        if set(values) != set(expected):
            raise ValueError("missing or selected calibration outcomes cannot change denominator")
        scores = [_float(values[k]) for k in expected]
        if any(not 0 <= s <= 1 for s in scores):
            raise ValueError("unknown infrastructure outcomes are not numeric financial zero")
        means[arm] = math.fsum(scores) / 360
    versus_static = means["positive"] - means["Static"]
    versus_reverse = means["positive"] - means["reverse"]
    return dict(
        denominator_per_direction=360,
        means=means,
        positive_minus_Static=versus_static,
        positive_minus_reverse=versus_reverse,
        observed_numeric_positive_vs_Static=versus_static > 0,
        only_less_harmed_than_reverse=versus_static <= 0 and versus_reverse > 0,
        checkpoint_selection_allowed=False,
        actual_evaluation_provenance_verified=False,
        statistical_significance_established=False,
    )
