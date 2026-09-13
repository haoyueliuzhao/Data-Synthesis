"""Finite-support novelty and exact frozen-potential dual-KL updates.

The input prior is the unchanged pi0 material pushforward, not an estimated
Teacher law. Controls remain exactly at their original prior. Probabilities
are never clipped or renormalized after the log-space softmax solution.
"""

import math
from fractions import Fraction

from .protocol import (
    CONTRIBUTION_EXPONENT,
    EPSILON,
    LAMBDA_CURRENT,
    LAMBDA_PRIOR,
    NOVELTY_EXPONENT,
    NOVELTY_TEMPERATURE,
    RMS_FLOOR,
    record,
    require,
)


def _scalar(value):
    require(not isinstance(value, bool), "distribution.boolean_not_scalar")
    try:
        number = float(Fraction(value)) if isinstance(value, str) else float(value)
    except (TypeError, ValueError, ZeroDivisionError, OverflowError) as error:
        raise ValueError("distribution.finite_scalar") from error
    require(math.isfinite(number), "distribution.finite_scalar")
    return number


def _inputs(pi, prior, contributions, mu, controls):
    require(
        isinstance(pi, dict) and pi and set(pi) == set(prior) == set(contributions) == set(mu),
        "distribution.same_task_support",
    )
    require(set(controls) <= set(pi), "distribution.registered_control_tasks")
    probability, anchor, scores, mass = {}, {}, {}, {}
    for task in sorted(pi):
        require(
            pi[task] and set(pi[task]) == set(prior[task]) == set(contributions[task]),
            "distribution.same_state_support",
        )
        probability[task] = {state: _scalar(pi[task][state]) for state in sorted(pi[task])}
        anchor[task] = {state: _scalar(prior[task][state]) for state in sorted(prior[task])}
        scores[task] = {
            state: _scalar(contributions[task][state]) for state in sorted(contributions[task])
        }
        mass[task] = _scalar(mu[task])
        for values in (probability[task], anchor[task]):
            require(
                all(value > 0 for value in values.values())
                and math.isclose(math.fsum(values.values()), 1.0, rel_tol=0, abs_tol=1e-12),
                "distribution.interior_simplex_no_probability_repair",
            )
        require(mass[task] > 0, "distribution.positive_task_mass")
        centered = math.fsum(
            probability[task][state] * value for state, value in scores[task].items()
        )
        require(
            abs(centered) <= 1e-10 * max(1.0, *(abs(value) for value in scores[task].values())),
            "distribution.centered_Contribution_required",
        )
        if task in controls:
            require(
                probability[task] == anchor[task],
                "distribution.control_current_equals_original_prior",
            )
    require(
        math.isclose(math.fsum(mass.values()), 1.0, rel_tol=0, abs_tol=1e-12),
        "distribution.task_marginal_simplex",
    )
    return probability, anchor, scores, mass


def contribution_temperatures(C, pi, mu, *, control_tasks=(), rms_floor=RMS_FLOOR):
    """T_C(x)=mu(x)*max(noncontrol normalized mu*pi RMS(C/mu), floor)."""
    controls = set(control_tasks)
    pi, _, C, mu = _inputs(pi, pi, C, mu, controls)
    floor = _scalar(rms_floor)
    require(floor > 0, "distribution.positive_RMS_floor")
    selected = [task for task in pi if task not in controls]
    require(selected, "distribution.noncontrol_optimization_population")
    total_mass = math.fsum(_scalar(mu[task]) for task in selected)
    values = [
        (_scalar(mu[task]) * _scalar(pi[task][state]), _scalar(C[task][state]) / _scalar(mu[task]))
        for task in selected
        for state in pi[task]
    ]
    require(all(math.isfinite(value) for _, value in values), "distribution.finite_C_over_mu")
    maximum = max(abs(value) for _, value in values)
    rms = (
        maximum
        * math.sqrt(
            math.fsum(weight * (value / maximum) ** 2 for weight, value in values) / total_mass
        )
        if maximum
        else 0.0
    )
    scale = max(rms, floor)
    temperatures = {task: _scalar(mu[task]) * scale for task in selected}
    require(
        all(value > 0 and math.isfinite(value) for value in temperatures.values()),
        "distribution.finite_positive_contribution_temperature",
    )
    return record(
        "Contribution_temperature",
        global_weighted_RMS=rms,
        RMS_floor=floor,
        global_scale_after_floor=scale,
        noncontrol_total_mu=total_mass,
        included_tasks=sorted(selected),
        excluded_control_tasks=sorted(controls),
        T_C=temperatures,
        weighting="mu(x)*pi(z|x), divided by total noncontrol mu",
        empirical_proxy_all_zero=maximum == 0,
        information_status="UNINFORMATIVE_ZERO_EMPIRICAL_PROXY"
        if maximum == 0
        else "NONZERO_EMPIRICAL_PROXY",
        zero_proxy_proves_theoretical_Contribution_zero=False,
    )


def _sigmoid(value):
    if value >= 0:
        return 1 / (1 + math.exp(-value))
    exponential = math.exp(value)
    return exponential / (1 + exponential)


def _kl(values, reference):
    return math.fsum(
        probability * (math.log(probability) - math.log(reference[state]))
        for state, probability in values.items()
    )


def anchored_update(
    pi,
    pi0,
    C,
    mu,
    *,
    control_tasks=(),
    contribution_only=False,
    epsilon=EPSILON,
    contribution_exponent=CONTRIBUTION_EXPONENT,
    novelty_exponent=NOVELTY_EXPONENT,
    novelty_temperature=NOVELTY_TEMPERATURE,
    lambda_current=LAMBDA_CURRENT,
    lambda_prior=LAMBDA_PRIOR,
    rms_floor=RMS_FLOOR,
):
    """Solve the exact dual-KL proximal problem with this round's potential fixed.

    Returns actual floating-point probabilities. Fraction strings are accepted
    for the original pi0 and mu. An underflowed zero is rejected, never repaired.
    C-only keeps the registered Contribution exponent; it only sets b to zero.
    """
    controls = set(control_tasks)
    probability, prior, scores, mass = _inputs(pi, pi0, C, mu, controls)
    eps, a, declared_b, TN, current, historic = map(
        _scalar,
        (
            epsilon,
            contribution_exponent,
            novelty_exponent,
            novelty_temperature,
            lambda_current,
            lambda_prior,
        ),
    )
    require(
        0 < eps < 0.5
        and 0 <= a <= 1
        and 0 <= declared_b <= 1
        and TN > 0
        and current > 0
        and historic > 0,
        "distribution.registered_parameter_domain",
    )
    b = 0.0 if contribution_only else declared_b
    temperature = contribution_temperatures(
        scores, probability, mass, control_tasks=controls, rms_floor=rms_floor
    )
    updated, diagnostics = {}, {}
    regularization = current + historic
    for task in probability:
        old, anchor, values = probability[task], prior[task], scores[task]
        novelty = {state: max(0.0, math.log(anchor[state]) - math.log(old[state])) for state in old}
        mapped_novelty = {
            state: eps + (1 - 2 * eps) * (-math.expm1(-value / TN))
            for state, value in novelty.items()
        }
        if task in controls:
            # Controls have an identity update and a neutral diagnostic potential.
            # Their C is retained but never used in RMS or potential optimization.
            mapped_contribution = {state: None for state in old}
            log_potential = {state: 0.0 for state in old}
            potential = {state: 1.0 for state in old}
            result = dict(old)
            normalizer = None
            residual = 0.0
        else:
            mapped_contribution = {
                state: eps + (1 - 2 * eps) * _sigmoid(value / temperature["T_C"][task])
                for state, value in values.items()
            }
            log_potential = {
                state: a * math.log(mapped_contribution[state])
                + b * math.log(mapped_novelty[state])
                for state in old
            }
            potential = {state: math.exp(value) for state, value in log_potential.items()}
            logits = {
                state: (
                    current * math.log(old[state])
                    + historic * math.log(anchor[state])
                    + log_potential[state]
                )
                / regularization
                for state in old
            }
            maximum = max(logits.values())
            normalizer = maximum + math.log(
                math.fsum(math.exp(value - maximum) for value in logits.values())
            )
            result = {state: math.exp(value - normalizer) for state, value in logits.items()}
            require(
                all(value > 0 and math.isfinite(value) for value in result.values()),
                "distribution.softmax_underflow_or_nonfinite_STOP_no_clipping",
            )
            require(
                math.isclose(math.fsum(result.values()), 1.0, rel_tol=0, abs_tol=1e-12),
                "distribution.softmax_simplex_no_posthoc_normalization",
            )
            stationarity = {
                state: log_potential[state]
                - current * (math.log(result[state]) - math.log(old[state]))
                - historic * (math.log(result[state]) - math.log(anchor[state]))
                for state in old
            }
            center = math.fsum(result[state] * value for state, value in stationarity.items())
            residual = max(abs(value - center) for value in stationarity.values())
            require(
                residual <= 1e-9 * max(1.0, abs(center)),
                "distribution.proximal_stationarity_residual",
            )
        updated[task] = result
        kl_current, kl_prior = _kl(result, old), _kl(result, anchor)
        diagnostics[task] = {
            "optimized": task not in controls,
            "mu": mass[task],
            "C": values,
            "N": novelty,
            "C_tilde": mapped_contribution,
            "N_tilde": mapped_novelty,
            "Phi": potential,
            "log_Phi": log_potential,
            "T_C": temperature["T_C"].get(task),
            "T_N": TN,
            "pi_current": old,
            "r_pi0": anchor,
            "pi_next": result,
            "KL_next_to_current": kl_current,
            "KL_next_to_prior": kl_prior,
            "TV_next_current": 0.5 * math.fsum(abs(result[state] - old[state]) for state in old),
            "entropy_next": -math.fsum(value * math.log(value) for value in result.values()),
            "optimality_residual": residual,
            "softmax_log_normalizer": normalizer,
            "frozen_potential_objective": math.fsum(
                result[state] * log_potential[state] for state in old
            )
            - current * kl_current
            - historic * kl_prior,
            "control_neutral_potential_not_Contribution_optimization": task in controls,
        }
    return record(
        "anchored_distribution_update",
        pi_next=updated,
        task_diagnostics=diagnostics,
        temperature=temperature,
        epsilon=eps,
        contribution_exponent=a,
        declared_novelty_exponent=declared_b,
        effective_novelty_exponent=b,
        contribution_only=bool(contribution_only),
        novelty_temperature=TN,
        lambda_current=current,
        lambda_prior=historic,
        prior_is_fixed_pi0=True,
        control_tasks=sorted(controls),
        controls_exactly_preserved=True,
        weighted_KL_next_current=math.fsum(
            mass[task] * row["KL_next_to_current"] for task, row in diagnostics.items()
        ),
        weighted_KL_next_prior=math.fsum(
            mass[task] * row["KL_next_to_prior"] for task, row in diagnostics.items()
        ),
        weighted_TV=math.fsum(
            mass[task] * row["TV_next_current"] for task, row in diagnostics.items()
        ),
        weighted_entropy=math.fsum(
            mass[task] * row["entropy_next"] for task, row in diagnostics.items()
        ),
        maximum_optimality_residual=max(row["optimality_residual"] for row in diagnostics.values()),
        exact_frozen_potential_dual_KL_solution=True,
        probability_clipping_or_repair=False,
        true_task_utility_monotonicity_guaranteed=False,
        feedback_scope=(
            "one-step stochastic trajectory proxy, not exact multistep or greedy utility"
        ),
    )
