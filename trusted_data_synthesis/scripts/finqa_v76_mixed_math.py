"""V76 fixed-teacher objective and its clip-aware AdamW one-step derivative.

Only the original old-state simplex is adjustable. Teacher suffix gradients are
fixed additive terms in G, while their mass reduces the old task loss once.
No models, files, processes, or scientific entry points are opened here.
"""
from __future__ import annotations

import copy
import math
from fractions import Fraction


def require(ok, message):
    if not ok:
        raise ValueError('V76 mixed objective: ' + message)


def _adam(module=None):
    if module is not None:
        return module
    from trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo import optimizer_pullback
    return optimizer_pullback


def fixed_weights(material, tasks):
    """Fixed V75 slots; absent teacher mass stays in the old objective."""
    output = {}
    require(set(material['tasks']) <= set(tasks), 'teacher task outside original support')
    for task in tasks:
        slots = material['tasks'].get(task, {}).get('slots', {})
        require(set(slots) <= {'initial', 'post'}, 'unknown teacher slot')
        values = {key: Fraction(1, 4) if slots.get(key) is not None else Fraction(0)
                  for key in ('initial', 'post')}
        values['old'] = Fraction(1) - values['initial'] - values['post']
        output[task] = {key: str(value) for key, value in values.items()}
    return output


def validate_weights(weights, pi):
    require(set(weights) == set(pi), 'weights must cover every original task')
    for row in weights.values():
        require(set(row) == {'old', 'initial', 'post'}, 'exact fixed slots required')
        initial, post, old = (Fraction(str(row[k])) for k in ('initial', 'post', 'old'))
        require(initial in (0, Fraction(1, 4)) and post in (0, Fraction(1, 4))
                and old == 1-initial-post, 'fixed quarter slots or retained old mass changed')
    return weights


def _teacher_values(teachers, task, weights, reference):
    import torch
    expected = [key for key in ('initial', 'post') if Fraction(str(weights[task][key]))]
    require(task in teachers and list(teachers[task]) == expected,
            'complete fixed teacher gradients required: '+task)
    for slot in expected:
        value = teachers[task][slot]
        require(list(value) == list(reference), 'teacher parameter order changed')
        for name, tensor in value.items():
            other = reference[name]
            require(isinstance(tensor, torch.Tensor) and tensor.shape == other.shape
                    and tensor.dtype == other.dtype and tensor.device == other.device
                    and not tensor.requires_grad and bool(torch.isfinite(tensor).all()),
                    'teacher tensor coordinate, dtype or finite value changed')
        yield slot, value


def aggregate_mixed_gradient(gradients, teachers, pi, mu, weights, *, adam=None):
    """Original task/state/parameter order, then fixed teacher slots per task."""
    import torch
    adam = _adam(adam)
    validate_weights(weights, pi)
    first = adam._population(gradients, pi, mu)
    require(set(teachers) == set(pi), 'no missing/extra teacher task containers')
    result = {name: torch.zeros_like(value) for name, value in first.items()}
    for task in sorted(gradients):
        mass = float(Fraction(str(mu[task])))
        c = float(Fraction(str(weights[task]['old'])))
        for state in sorted(gradients[task]):
            coefficient = mass*c*float(Fraction(str(pi[task][state])))
            for name, value in gradients[task][state].items():
                result[name].add_(value.detach(), alpha=coefficient)
        for slot, values in _teacher_values(teachers, task, weights, first):
            coefficient = mass*float(Fraction(str(weights[task][slot])))
            for name, value in values.items():
                result[name].add_(value.detach(), alpha=coefficient)
    return result


def prepare_virtual_point(parameters, optimizer, gradients, teachers, pi, mu, weights,
                          *, clip_max_norm=1.0, adam=None):
    adam = _adam(adam)
    binding = adam.bind_adamw(parameters, optimizer, clip_max_norm=clip_max_norm)
    G = aggregate_mixed_gradient(gradients, teachers, pi, mu, weights, adam=adam)
    return dict(binding=binding, G=G, **adam.virtual_step(binding, G),
                mixture_weights=copy.deepcopy(weights), teacher_fixed_outside_pi=True)


def centered_contributions(gradients, pi, mu, a, weights, *, adam=None):
    """C_xz = mu_x c_x <a,g_xz - sum_z pi_xz g_xz>; c appears once."""
    adam = _adam(adam)
    validate_weights(weights, pi)
    original = adam.centered_contributions(gradients, pi, mu, a)
    C = {task: {state: float(Fraction(str(weights[task]['old'])))*value
                for state, value in states.items()} for task, states in original['C'].items()}
    residuals = {task: math.fsum(float(Fraction(str(pi[task][state])))*value
                               for state, value in states.items()) for task, states in C.items()}
    for task, residual in residuals.items():
        require(abs(residual) <= 1e-10*max(1.0, *(abs(v) for v in C[task].values())),
                'centered mixed C residual')
    return dict(C=C, center_residuals=residuals,
        diagnostics=dict(schema='v76_fixed_teacher_centered_C.v1',
            formula='mu_x*c_x*<a,g_xz-sum_z(pi_xz*g_xz)>',
            old_mass_applied_once=True, teacher_support_not_added_to_pi=True,
            teacher_gradients_affect_G_and_Adam_Jacobian=True,
            C=C, center_residuals=residuals,
            original_centered_diagnostics=original['diagnostics']))


def update_distribution(prepared, gradients, gJ, pi, prior, mu, weights,
                        *, feedback_report, control_tasks=(), adam=None,
                        parameter_digest=None, **parameters):
    """Caller reconstructs and matches the sealed mixed G/theta_bar exactly once."""
    from trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo import distribution
    from trusted_synthesis.finance_research import v6_distribution
    if parameter_digest is None:
        from trusted_synthesis.finance_research.providers import parameter_digest
    require(prepared.get('teacher_fixed_outside_pi') is True
            and prepared['mixture_weights'] == weights,
            'virtual point was not made with the registered mixed objective')
    require(feedback_report.get('denominator') == 700
            and feedback_report.get('all_receipts_validated') is True
            and feedback_report.get('gJ_digest') == parameter_digest(gJ)
            and feedback_report.get('parameter_digest') == parameter_digest(prepared['theta_bar']),
            'complete same-virtual-point reward/700 gradient required')
    adam = _adam(adam)
    pulled = adam.pullback(prepared['binding'], prepared['G'], {name: -v for name,v in gJ.items()})
    centered = centered_contributions(gradients, pi, mu, pulled['a'], weights, adam=adam)
    all_zero = feedback_report.get('accounting', {}).get('zero_reward_trajectories_skipped', 0) == 700
    update = (v6_distribution.automatic_update(pi, prior, centered['C'], mu,
        arm='Full', feedback_all_zero=True) if all_zero else
        distribution.anchored_update(pi, prior, centered['C'], mu, control_tasks=control_tasks,
                                     contribution_only=False, **parameters))
    return dict(distribution=update, C=centered['C'], a=pulled['a'],
        pullback_diagnostics=pulled['diagnostics'], contribution_diagnostics=centered['diagnostics'],
        feedback_report=feedback_report, exact_multistep_value_derivative=False,
        teacher_fixed_outside_pi=True, old_mass_applied_once=True)
