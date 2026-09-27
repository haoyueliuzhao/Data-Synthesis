"""Bridge to the current clip-aware AdamW / centered-C / novelty kernel.

No historical launcher, hardcoded population size, model, or GPU starts here.
"""

from __future__ import annotations

import copy
import math
from fractions import Fraction


def _adam():
    from trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo import optimizer_pullback

    return optimizer_pullback


def prepare_virtual_point(
    named_parameters, optimizer, state_gradients, pi, mu, *, clip_max_norm=1.0
):
    """Create theta_bar BEFORE collecting feedback there; leave real AdamW untouched."""
    adam = _adam()
    binding = adam.bind_adamw(named_parameters, optimizer, clip_max_norm=clip_max_norm)
    population = adam.aggregate_gradient(state_gradients, pi, mu)
    virtual = adam.virtual_step(binding, population)
    return {"binding": binding, "G": population, **virtual}


def update_distribution(
    prepared,
    state_gradients,
    gJ,
    pi,
    pi0,
    mu,
    *,
    feedback_report,
    control_tasks=(),
    contribution_only=False,
    **update_parameters,
):
    """Use complete native-reward gJ, preserving the actual C/N/pi diagnostics."""
    from trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo import distribution

    from .providers import parameter_digest

    if (
        feedback_report.get("denominator", 0) <= 0
        or feedback_report.get("all_receipts_validated") is not True
        or feedback_report.get("gJ_digest") != parameter_digest(gJ)
        or feedback_report.get("parameter_digest") != parameter_digest(prepared["theta_bar"])
    ):
        raise ValueError("kernel requires complete gJ sampled at its actual virtual point")
    adam = _adam()
    if parameter_digest(adam.aggregate_gradient(state_gradients, pi, mu)) != parameter_digest(
        prepared["G"]
    ):
        raise ValueError("class gradients/distribution changed after virtual-point creation")
    pullback = adam.pullback(
        prepared["binding"], prepared["G"], {name: -value for name, value in gJ.items()}
    )
    centered = adam.centered_contributions(state_gradients, pi, mu, pullback["a"])
    # Preserve the current zero-feedback rule: novelty motion is not evidence of a
    # useful training direction when every feedback reward is zero.
    all_zero = (
        feedback_report.get("accounting", {}).get("zero_reward_trajectories_skipped", 0)
        == feedback_report["denominator"]
    )
    if all_zero:
        result = {
            "pi_next": copy.deepcopy(pi),
            "status": "UNINFORMATIVE_FEEDBACK",
            "pi_exactly_unchanged": True,
            "theoretical_Contribution_zero": False,
            "N": {
                task: {
                    state: max(
                        0.0,
                        math.log(float(Fraction(str(pi0[task][state]))))
                        - math.log(float(Fraction(str(probability)))),
                    )
                    for state, probability in states.items()
                }
                for task, states in pi.items()
            },
        }
    else:
        result = distribution.anchored_update(
            pi,
            pi0,
            centered["C"],
            mu,
            control_tasks=control_tasks,
            contribution_only=contribution_only,
            **update_parameters,
        )
    return {
        "distribution": result,
        "C": centered["C"],
        "a": pullback["a"],
        "pullback_diagnostics": pullback["diagnostics"],
        "contribution_diagnostics": centered["diagnostics"],
        "feedback_report": feedback_report,
        "exact_multistep_value_derivative": False,
    }
