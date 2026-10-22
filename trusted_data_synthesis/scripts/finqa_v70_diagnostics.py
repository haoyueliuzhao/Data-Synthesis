"""V70 CPU-only frozen-contribution references, never training distributions.

The caller supplies already sealed formal/draw updates and their provenance.
This module neither opens artifacts nor imports a model, optimizer, or GPU stack.
It reuses the original frozen map: C smoothing and RMS stay fixed, N follows p.
"""
from __future__ import annotations

import copy
import math
from fractions import Fraction

from trusted_synthesis.finance_research import v6_distribution as distribution

MAX_ITERATIONS = 100
HILBERT_TOLERANCE = 1e-8
FIRST_STEP_ABS_TOLERANCE = 1e-12
FIRST_STEP_HILBERT_TOLERANCE = 1e-10
ROUNDING_TOLERANCE = 1e-10
RHO = 0.8


def policy():
    return dict(
        schema="v70_frozen_reference_policy.v1", arithmetic="Python binary64 (FP64)",
        max_iterations=MAX_ITERATIONS, max_adjustable_Hilbert_tolerance=HILBERT_TOLERANCE,
        first_step_max_absolute_tolerance=FIRST_STEP_ABS_TOLERANCE,
        first_step_max_Hilbert_tolerance=FIRST_STEP_HILBERT_TOLERANCE,
        rounding_tolerance=ROUNDING_TOLERANCE, parameters=dict(distribution.PARAMETERS),
        frozen_fields=["C", "C_tilde", "temperature", "T_C", "prior", "mu"],
        novelty_recomputed_from_each_internal_p=True, formal_q_not_replaced_by_reference=True,
        adjustable_tasks="support size greater than one", adjustable_weights="mu / sum_adjustable_mu",
        Hilbert_product_metric="maximum over adjustable tasks",
        draw_sensitivity_is_variance_estimate=False, draw_sensitivity_is_confidence_interval=False,
        formal_q_is_average_of_draw_q=False, all_zero_feedback_is_convergence=False,
        contraction_certificate_excludes_uninformative_identity_branch=True,
        real_points=3, target_drift_observations=2, statistical_convergence_proof=False,
        automatic_experiment_extension=False,
        model_calls=0, backward_passes=0, GPU_work=0, external_API_calls=0,
    )


def _require(condition, message):
    if not condition:
        raise ValueError("v70_diagnostics: " + message)


def _scalar(value):
    _require(not isinstance(value, bool), "boolean is not a scalar")
    number = float(Fraction(value)) if isinstance(value, str) else float(value)
    _require(math.isfinite(number), "nonfinite scalar")
    return number


def _population(current, prior, mu):
    _require(isinstance(current, dict) and current and set(current) == set(prior) == set(mu),
             "task support must match")
    p, r = {}, {}
    mass = {task: _scalar(value) for task, value in mu.items()}
    _require(min(mass.values()) > 0 and math.isclose(math.fsum(mass.values()), 1.0,
             rel_tol=0, abs_tol=1e-12), "mu must be a positive simplex")
    for task in current:
        p[task] = distribution._positive(current[task], simplex=True)
        r[task] = distribution._positive(prior[task], simplex=True)
        _require(set(p[task]) == set(r[task]), "state support must match")
    return p, r, mass


def distribution_distances(left, right, mu):
    """Both directional KLs, TV and Hilbert; no clipping or mass repair."""
    left, right, mass = _population(left, right, mu)
    adjustable = [task for task in left if len(left[task]) > 1]
    adjustable_mass = math.fsum(mass[task] for task in adjustable)
    rows = {}
    for task, p in left.items():
        q = right[task]
        rows[task] = dict(
            TV=0.5 * math.fsum(abs(p[s] - q[s]) for s in p),
            KL_left_to_right=math.fsum(p[s] * (math.log(p[s]) - math.log(q[s])) for s in p),
            KL_right_to_left=math.fsum(q[s] * (math.log(q[s]) - math.log(p[s])) for s in p),
            Hilbert=distribution.oscillation_distance(p, q),
        )
    def aggregate(tasks, total):
        if not tasks:
            return None
        return dict(**{key: math.fsum(mass[t] * rows[t][key] / total for t in tasks)
                       for key in ("TV", "KL_left_to_right", "KL_right_to_left", "Hilbert")},
                    max_Hilbert=max(rows[t]["Hilbert"] for t in tasks))
    return dict(per_task=rows, all_tasks=aggregate(list(left), 1.0),
                adjustable=aggregate(adjustable, adjustable_mass),
                adjustable_tasks=adjustable, adjustable_mu=adjustable_mass)


def _match(left, right, mu):
    distances = distribution_distances(left, right, mu)
    maximum = max(abs(_scalar(left[t][s]) - _scalar(right[t][s])) for t in left for s in left[t])
    hilbert = distances["all_tasks"]["max_Hilbert"]
    return dict(max_absolute_difference=maximum, max_Hilbert=hilbert,
                passed=maximum <= FIRST_STEP_ABS_TOLERANCE and hilbert <= FIRST_STEP_HILBERT_TOLERANCE)


def _frozen_inputs(current, prior, mu, update):
    """Bind the original formal smoothing/scales without recomputing RMS."""
    controls = set(update.get("control_tasks", ()))
    _require(update.get("contribution_only") is False
             and controls == {task for task in current if len(current[task]) == 1},
             "the registered Full update with exactly singleton control tasks is required")
    for key, expected in distribution.PARAMETERS.items():
        if key == "novelty_exponent":
            _require(update.get("effective_novelty_exponent") == expected
                     and update.get("declared_novelty_exponent") == expected, "Full novelty changed")
        elif key == "rms_floor":
            _require(update["temperature"]["RMS_floor"] == expected, "RMS floor changed")
        else:
            _require(update.get(key) == expected, "registered parameter changed: " + key)
    rows = update["task_diagnostics"]
    _require(set(rows) == set(current), "formal diagnostic task support changed")
    scores, smooth, temperatures = {}, {}, {}
    temperature = copy.deepcopy(update["temperature"])
    rms, scale = (_scalar(temperature[key]) for key in ("global_weighted_RMS", "global_scale_after_floor"))
    _require(rms >= 0 and scale == max(rms, distribution.PARAMETERS["rms_floor"]), "saved RMS scale differs")
    for task, row in rows.items():
        _require(row["optimized"] is (task not in controls) and row["pi_current"] == current[task]
                 and row["r_pi0"] == prior[task] and row["mu"] == mu[task]
                 and row["pi_next"] == update["pi_next"][task], "formal point binding differs")
        scores[task], smooth[task] = copy.deepcopy(row["C"]), copy.deepcopy(row["C_tilde"])
        if task in controls:
            temperatures[task] = None
            _require(current[task] == prior[task] == update["pi_next"][task]
                     and list(current[task].values()) == [1.0]
                     and row["T_C"] is None and task not in temperature["T_C"]
                     and list(smooth[task].values()) == [None], "singleton control diagnostic changed")
        else:
            temperatures[task] = _scalar(row["T_C"])
            _require(set(smooth[task]) == set(current[task])
                     and temperatures[task] == temperature["T_C"][task] == mu[task] * scale,
                     "saved contribution scale or support differs")
    # Original kernel validation covers centering, finite C and positive support.
    distribution.kernel._inputs(current, prior, scores, mu, controls)
    return dict(C=scores, C_tilde=smooth, temperature=temperature, T_C=temperatures,
                prior=copy.deepcopy(prior), mu=copy.deepcopy(mu),
                control_tasks=sorted(controls), parameters=dict(distribution.PARAMETERS))


def frozen_reference(*, current, prior, mu, update, feedback_all_zero):
    """Analyze one formal (700) or draw (350) update; allzero is not convergence."""
    _require(type(feedback_all_zero) is bool, "explicit boolean feedback_all_zero required")
    p, r, mass = _population(current, prior, mu)
    q, _, _ = _population(update["pi_next"], r, mass)
    movement = distribution_distances(q, p, mass)
    adjustable = movement["adjustable_tasks"]
    base = dict(current=p, prior=r, mu=mass, formal_q=q, R=movement,
                reference_is_training_distribution=False, iterations=0,
                numeric_convergence=False, fixed_point=None, G=None,
                feedback_all_zero=feedback_all_zero)
    if feedback_all_zero:
        _require(update.get("status") == "UNINFORMATIVE_FEEDBACK" and p == q,
                 "allzero branch must preserve pi exactly and be explicitly uninformative")
        return dict(base, status="UNINFORMATIVE_FEEDBACK", frozen_inputs=None,
                    first_step_match=None, trace=[], certificate=None,
                    fixed_point_residual_upper_bound=None)
    frozen = _frozen_inputs(p, r, mass, update)
    certificate = distribution.contraction_certificate()
    _require(certificate["certified_contraction_factor"] == RHO, "rho .8 certificate failed")
    base.update(frozen_inputs=frozen, certificate=certificate)
    if not adjustable:
        _require(p == q, "singleton update unexpectedly changed")
        return dict(base, status="NO_ADJUSTABLE_TASKS", first_step_match=_match(p, q, mass),
                    trace=[], fixed_point_residual_upper_bound=None)
    trace, previous, point = [], None, copy.deepcopy(p)
    first_match = None
    final_residuals = None
    for iteration in range(1, MAX_ITERATIONS + 1):
        next_point = {task: distribution.frozen_contribution_step(point[task], r[task], frozen["C_tilde"][task])
                      if task in adjustable else dict(point[task])
                      for task in point}
        residuals = {task: distribution.oscillation_distance(point[task], next_point[task]) for task in point}
        maximum = max(residuals[task] for task in adjustable)
        if first_match is None:
            first_match = _match(next_point, q, mass)
            _require(first_match["passed"], "first frozen step does not match the formal Full q")
        excess = None if previous is None else max(residuals[t] - RHO * previous[t] for t in adjustable)
        _require(excess is None or excess <= ROUNDING_TOLERANCE,
                 "observed frozen-map Hilbert contraction certificate failed")
        trace.append(dict(iteration=iteration, max_adjustable_Hilbert_update=maximum,
                          adjustable_weighted_Hilbert_update=math.fsum(
                              mass[t] * residuals[t] / movement["adjustable_mu"] for t in adjustable),
                          all_task_weighted_Hilbert_update=math.fsum(mass[t] * residuals[t] for t in point),
                          maximum_per_task_contraction_excess=excess))
        point, previous, final_residuals = next_point, residuals, residuals
        if maximum <= HILBERT_TOLERANCE:
            break
    converged = trace[-1]["max_adjustable_Hilbert_update"] <= HILBERT_TOLERANCE
    # The saved reference is F(p_last): its unobserved next residual is bounded
    # by rho times the last observed residual, with the registered arithmetic
    # allowance, without a 101st map application. This is not interval arithmetic.
    upper = {t: RHO * final_residuals[t] + (ROUNDING_TOLERANCE if t in adjustable else 0.0)
             for t in point}
    base.update(status="NUMERICALLY_CONVERGED_FROZEN_REFERENCE" if converged else "MAX_ITERATIONS_REACHED",
                numeric_convergence=converged, iterations=len(trace), first_step_match=first_match,
                fixed_point=point, G=distribution_distances(p, point, mass), trace=trace,
                final_observed_update_residuals=final_residuals,
                fixed_point_residual_upper_bound=upper,
                residual_bound_is_theory_plus_registered_roundoff_not_interval_arithmetic=True,
                distance_to_exact_fixed_point_upper_bound={t: upper[t] / (1 - RHO) for t in point},
                real_closed_loop_convergence_proved=False)
    return base


def analyze_frozen_point(*, current, prior, mu, formal_update, draw_updates,
                         feedback_all_zero, draw_feedback_all_zero, binding):
    """Freeze full/draw diagnostics. Caller seals this return as a separate artifact.

    ``draw_updates`` is a two-key dict of original 350-denominator updates; its
    keys also occur in ``draw_feedback_all_zero``. ``binding`` is an opaque,
    nonempty scientific provenance object checked and supplied by the caller.
    No normalized draw q is averaged or substituted for formal q.
    """
    _require(isinstance(binding, dict) and binding, "nonempty scientific provenance required")
    _require(isinstance(draw_updates, dict) and len(draw_updates) == 2
             and set(draw_updates) == set(draw_feedback_all_zero), "exactly two bound draw updates required")
    _require(type(feedback_all_zero) is bool
             and all(type(flag) is bool for flag in draw_feedback_all_zero.values())
             and feedback_all_zero == all(draw_feedback_all_zero.values()),
             "full/draw actual reward allzero flags contradict")
    formal = frozen_reference(current=current, prior=prior, mu=mu, update=formal_update,
                              feedback_all_zero=feedback_all_zero)
    draws = {key: frozen_reference(current=current, prior=prior, mu=mu, update=value,
                                  feedback_all_zero=draw_feedback_all_zero[key])
             for key, value in draw_updates.items()}
    a, b = draws.values()
    sensitivity = dict(
        status="COMPLETE" if a["numeric_convergence"] and b["numeric_convergence"] else "REFERENCE_UNAVAILABLE_OR_NOT_CONVERGED",
        one_step=distribution_distances(a["formal_q"], b["formal_q"], mu),
        reference=distribution_distances(a["fixed_point"], b["fixed_point"], mu)
                  if a["fixed_point"] is not None and b["fixed_point"] is not None else None,
        variance_estimate=False, confidence_interval=False, formal_q_averaged=False,
        independent_feedback_draws=True, independence_is_caller_provenance_not_estimated=True)
    return dict(schema="v70_frozen_point_diagnostic.v1", policy=policy(), binding=copy.deepcopy(binding),
                formal=formal, draws=draws, draw_sensitivity=sensitivity,
                scientific_distribution_mutated=False, new_model_calls=0, new_backward_passes=0)


def compare_frozen_points(previous, current):
    """Target drift and the Hilbert tracking inequality for consecutive real points.

    Frozen references have finite residual. Both the requested exact-reference
    inequality and the finite-reference version with registered arithmetic
    allowance are reported; these are FP64 diagnostics, not interval proofs.
    TV is descriptive only; no Hilbert certificate is silently applied to TV.
    """
    old, new = previous["formal"], current["formal"]
    _require(old["prior"] == new["prior"] and old["mu"] == new["mu"], "prior or task marginal changed")
    _require(old["formal_q"] == new["current"], "successor pi must equal previous actually applied formal q")
    result = dict(schema="v70_frozen_point_tracking.v1", previous_binding=copy.deepcopy(previous["binding"]),
                  current_binding=copy.deepcopy(current["binding"]), rho=RHO,
                  tracking_metric="Hilbert, maximum over adjustable tasks", TV_contraction_claim=False,
                  relation="E_next <= rho * E_previous + D_H_next", D=None, tracking=None)
    if not old["numeric_convergence"] or not new["numeric_convergence"]:
        return dict(result, status="UNAVAILABLE_UNINFORMATIVE_OR_UNCONVERGED_REFERENCE")
    drift = distribution_distances(old["fixed_point"], new["fixed_point"], old["mu"])
    tasks = drift["adjustable_tasks"]
    rows = {}
    for task in tasks:
        before = old["G"]["per_task"][task]["Hilbert"]
        after = new["G"]["per_task"][task]["Hilbert"]
        target = drift["per_task"][task]["Hilbert"]
        rhs = RHO * before + target
        slack = old["fixed_point_residual_upper_bound"][task]
        rows[task] = dict(E_previous=before, E_next=after, D_H_next=target, exact_reference_rhs=rhs,
                          finite_reference_allowance=slack,
                          exact_reference_relation_observed=after <= rhs + ROUNDING_TOLERANCE,
                          finite_reference_relation_passed=after <= rhs + slack + ROUNDING_TOLERANCE)
    def summary(weights):
        if weights is None:
            collect = lambda field: max(row[field] for row in rows.values())
        else:
            collect = lambda field: math.fsum(weights[t] * rows[t][field] for t in tasks)
        before, after, target = (collect(key) for key in ("E_previous", "E_next", "D_H_next"))
        rhs, slack = RHO * before + target, collect("finite_reference_allowance")
        return dict(E_previous=before, E_next=after, D_H_next=target, exact_reference_rhs=rhs,
                    finite_reference_allowance=slack,
                    exact_reference_relation_observed=after <= rhs + ROUNDING_TOLERANCE,
                    finite_reference_relation_passed=after <= rhs + slack + ROUNDING_TOLERANCE)
    tracking = dict(per_task=rows, maximum_adjustable=summary(None),
                    adjustable_weighted=summary({t: old["mu"][t] / drift["adjustable_mu"] for t in tasks}),
                    all_task_weighted=summary({t: old["mu"][t] for t in tasks}))
    _require(all(row["finite_reference_relation_passed"] for row in rows.values()),
             "finite-reference Hilbert tracking relation failed")
    return dict(result, status="COMPLETE", D=drift, tracking=tracking)
