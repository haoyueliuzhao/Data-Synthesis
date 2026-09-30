"""V6 pure distribution controls and Experiment 4's explicitly frozen maps.

No model, data collection, qualification, optimizer, or GPU entry points live here.
Automatic C-only/Full updates delegate to the unchanged anchored kernel. The
separate frozen-C map is a mathematical object, not that kernel's dynamic RMS loop.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import random
import subprocess
from fractions import Fraction
from pathlib import Path

from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory
from trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo import distribution as kernel

from .contracts import digest

ARMS = ("Static", "Manual+", "Manual-", "C-only", "Full")
OUTER_STEPS = (400, 800, 1200, 1600)
PARAMETERS = dict(
    epsilon=0.05,
    contribution_exponent=0.8,
    novelty_exponent=0.2,
    novelty_temperature=1.0,
    lambda_current=4.0,
    lambda_prior=1.0,
    rms_floor=1e-8,
)
DEFAULT_OUTPUT = Path(
    "/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/"
    "finance_research_20260928/finqa_v6_01/experiment4_01"
)


def design_metadata():
    return dict(
        arms=list(ARMS),
        main_candidate="Full",
        outer_steps=list(OUTER_STEPS),
        manual_alpha=2,
        first_mechanism_reverse_is_not_Manual=True,
        contribution_exponent=0.8,
        Full_novelty_exponent=0.2,
        C_only_novelty_exponent=0.0,
        prior_never_reset=True,
        training_started=False,
        real_closed_loop_convergence_proved=False,
    )


def _number(value):
    if isinstance(value, bool):
        raise ValueError("boolean is not a probability or scalar")
    result = float(Fraction(value)) if isinstance(value, str) else float(value)
    if not math.isfinite(result):
        raise ValueError("finite scalar required")
    return result


def _positive(values, *, simplex=False):
    if not isinstance(values, dict) or not values:
        raise ValueError("nonempty finite support required")
    result = {key: _number(value) for key, value in values.items()}
    if min(result.values()) <= 0:
        raise ValueError("full positive support required; no clipping or repair")
    if simplex and not math.isclose(math.fsum(result.values()), 1, rel_tol=0, abs_tol=1e-12):
        raise ValueError("normalized probabilities required; no repair")
    return result


def _same(*rows):
    if any(set(row) != set(rows[0]) for row in rows[1:]):
        raise ValueError("state support must agree exactly")


def _softmax(logits):
    maximum = max(logits.values())
    log_z = maximum + math.log(math.fsum(math.exp(x - maximum) for x in logits.values()))
    return _positive({key: math.exp(value - log_z) for key, value in logits.items()}, simplex=True)


def manual_distribution(prior, coarse, *, direction, registered_singleton_tasks=()):
    """Fixed odds tilt r*2**(+/- chi), not fixed 2/3 mass or a C-derived control.

    A single coarse group returns its original row values exactly, including any
    registered rational-string representation. All other rows use the formula's
    own normalizer, not a post-hoc clipping or mass repair.
    """
    if direction not in {"Manual+", "Manual-"}:
        raise ValueError("direction must be Manual+ or Manual-")
    _same(prior, coarse)
    if not prior:
        raise ValueError("task support cannot be empty")
    singletons = set(registered_singleton_tasks)
    if not singletons <= set(prior):
        raise ValueError("registered singleton task outside current support")
    result = {}
    for task, original in prior.items():
        row, chi = _positive(original, simplex=True), coarse[task]
        _same(row, chi)
        if task in singletons:
            if len(row) != 1 or list(chi.values()) != [None] or list(row.values()) != [1.0]:
                raise ValueError(
                    "registered true singleton requires one unit-mass state and null chi"
                )
            result[task] = copy.deepcopy(original)
            continue
        if any(type(value) is not int or value not in (0, 1) for value in chi.values()):
            raise ValueError("coarse projection must be registered binary integers")
        if len(set(chi.values())) == 1:
            result[task] = copy.deepcopy(original)
            continue
        sign = 1 if direction == "Manual+" else -1
        weights = {
            state: probability * 2 ** (sign * chi[state]) for state, probability in row.items()
        }
        normalizer = math.fsum(weights.values())
        result[task] = _positive(
            {state: value / normalizer for state, value in weights.items()}, simplex=True
        )
    return result


def first_direction_reverse(prior, q_plus):
    """Mirror the FIRST current=prior mechanism direction; refuse nonpositive mass."""
    _same(prior, q_plus)
    if not prior:
        raise ValueError("task support cannot be empty")
    result = {}
    for task in prior:
        r, q = _positive(prior[task], simplex=True), _positive(q_plus[task], simplex=True)
        _same(r, q)
        result[task] = _positive({state: 2 * r[state] - q[state] for state in r}, simplex=True)
    return result


def automatic_update(current, prior, C, mu, *, arm, feedback_all_zero=False):
    """Delegate exact C-only/Full math; caller supplies genuine centered C/provenance.

    Zero reward for every fixed-denominator feedback record is an explicit caller
    fact, not inferred from a zero C vector. That branch preserves current pi
    exactly and is NOT the contractive frozen-map theorem below.
    """
    if arm not in {"C-only", "Full"} or type(feedback_all_zero) is not bool:
        raise ValueError("automatic arm and explicit boolean feedback flag required")
    if feedback_all_zero:
        kernel._inputs(current, prior, C, mu, set())
        return dict(
            pi_next=copy.deepcopy(current),
            status="UNINFORMATIVE_FEEDBACK",
            arm=arm,
            pi_exactly_unchanged=True,
            novelty_only_motion=False,
            theoretical_Contribution_zero=False,
        )
    return kernel.anchored_update(
        current, prior, C, mu, contribution_only=arm == "C-only", **PARAMETERS
    )


def oscillation_distance(p, q):
    """Hilbert/projective distance on normalized positive probabilities."""
    p, q = _positive(p, simplex=True), _positive(q, simplex=True)
    _same(p, q)
    delta = [math.log(p[key]) - math.log(q[key]) for key in p]
    return max(delta) - min(delta)


def _map_parameters(rho, eta):
    if not (math.isfinite(rho) and 0 <= rho < 1 and math.isfinite(eta) and eta >= 0):
        raise ValueError("require 0<=rho<1 and finite eta>=0")


def fixed_potential_step(p, r, potential, *, rho=0.8, eta=0.2):
    _map_parameters(rho, eta)
    p, r, potential = _positive(p, simplex=True), _positive(r, simplex=True), _positive(potential)
    _same(p, r, potential)
    return _softmax(
        {
            s: rho * math.log(p[s]) + (1 - rho) * math.log(r[s]) + eta * math.log(potential[s])
            for s in p
        }
    )


def fixed_potential_limit(r, potential, *, rho=0.8, eta=0.2):
    _map_parameters(rho, eta)
    r, potential = _positive(r, simplex=True), _positive(potential)
    _same(r, potential)
    return _softmax({s: math.log(r[s]) + eta / (1 - rho) * math.log(potential[s]) for s in r})


def contraction_certificate(*, rho=0.8, eta=0.2, b=0.2, epsilon=0.05, temperature=1.0):
    _map_parameters(rho, eta)
    if not (
        0 < epsilon < 0.5
        and temperature > 0
        and math.isfinite(temperature)
        and b >= 0
        and math.isfinite(b)
    ):
        raise ValueError("positive finite novelty parameters required")
    correction = eta * b * (1 - 2 * epsilon) / (epsilon * temperature)
    proved = correction <= rho
    return dict(
        rho=rho,
        eta=eta,
        novelty_exponent=b,
        epsilon=epsilon,
        T_N=temperature,
        maximum_slope_subtraction=correction,
        scalar_slope_lower_bound=rho - correction,
        monotone_sufficient_condition=proved,
        certified_contraction_factor=rho if proved else None,
        failed_sufficient_condition_is_not_a_nonconvergence_proof=True,
        requires_fixed_smoothed_C_and_scales=True,
        requires_normalized_positive_probabilities=True,
        normalization_cross_zero_lemma="min(log p-log q)<=0<=max(log p-log q)",
        real_training_closed_loop_convergence=False,
    )


def frozen_contribution_step(
    p, r, smoothed_C, *, rho=0.8, eta=0.2, a=0.8, b=0.2, epsilon=0.05, temperature=1.0
):
    """Only N depends on p. No RMS, recentering, optimizer, or feedback is recomputed."""
    contraction_certificate(rho=rho, eta=eta, b=b, epsilon=epsilon, temperature=temperature)
    if not math.isfinite(a) or a < 0:
        raise ValueError("finite nonnegative contribution exponent required")
    p, r, c = _positive(p, simplex=True), _positive(r, simplex=True), _positive(smoothed_C)
    _same(p, r, c)
    if any(not epsilon <= value <= 1 - epsilon for value in c.values()):
        raise ValueError("fixed smoothed Contribution must be in its declared positive range")
    logits = {}
    for s in p:
        n = max(0.0, math.log(r[s]) - math.log(p[s]))
        mapped = epsilon + (1 - 2 * epsilon) * (-math.expm1(-n / temperature))
        logits[s] = (
            rho * math.log(p[s])
            + (1 - rho) * math.log(r[s])
            + eta * (a * math.log(c[s]) + b * math.log(mapped))
        )
    return _softmax(logits)


def numerical_demonstration():
    """Deterministic synthetic arithmetic only; examples are not FinQA observations."""
    r = dict(a=0.55, b=0.25, c=0.15, d=0.05)
    p, q = dict(a=0.1, b=0.2, c=0.3, d=0.4), dict(a=0.7, b=0.1, c=0.1, d=0.1)
    potential, smoothed_C = dict(a=0.2, b=0.7, c=0.4, d=0.9), dict(a=0.08, b=0.7, c=0.4, d=0.91)
    fixed, fixed_limit, full_p, full_q = (
        dict(p),
        fixed_potential_limit(r, potential),
        dict(p),
        dict(q),
    )
    trace = []
    for iteration in range(161):
        successor = frozen_contribution_step(full_p, r, smoothed_C)
        residual = oscillation_distance(full_p, successor)
        trace.append(
            dict(
                iteration=iteration,
                fixed_potential_pi=fixed,
                fixed_potential_distance_to_exact_limit=oscillation_distance(fixed, fixed_limit),
                frozen_C_pi=full_p,
                frozen_C_second_initial_pi=full_q,
                two_initial_distance=oscillation_distance(full_p, full_q),
                one_step_residual=residual,
                fixed_point_distance_upper_bound=residual / (1 - 0.8),
            )
        )
        fixed = fixed_potential_step(fixed, r, potential)
        full_p, full_q = successor, frozen_contribution_step(full_q, r, smoothed_C)
    rng, pairs = random.Random(20260928), []

    def probability():
        return _softmax({str(i): rng.uniform(-12, 12) for i in range(6)})

    for _ in range(256):
        rp, pp, qp = probability(), probability(), probability()
        cc = {s: rng.uniform(0.05, 0.95) for s in rp}
        before = oscillation_distance(pp, qp)
        after = oscillation_distance(
            frozen_contribution_step(pp, rp, cc), frozen_contribution_step(qp, rp, cc)
        )
        pairs.append(dict(before=before, after=after, ratio=after / before))
    prior = {"synthetic": r}
    raw = dict(a=-0.3, b=0.2, c=0.5, d=0.8)
    center = math.fsum(r[s] * raw[s] for s in r)
    C = {"synthetic": {s: raw[s] - center for s in r}}
    first = automatic_update(prior, prior, C, {"synthetic": 1}, arm="Full")
    first_c = automatic_update(prior, prior, C, {"synthetic": 1}, arm="C-only")
    reverse = first_direction_reverse(prior, first["pi_next"])
    coarse = {"synthetic": dict(a=0, b=1, c=0, d=1)}
    return dict(
        synthetic_only=True,
        inputs=dict(
            r=r, initial=p, second_initial=q, fixed_potential=potential, fixed_smoothed_C=smoothed_C
        ),
        iterations=trace,
        random_pair_checks=pairs,
        maximum_observed_pair_ratio=max(x["ratio"] for x in pairs),
        certificate=contraction_certificate(),
        fixed_potential_exact_limit=fixed_limit,
        Manual_plus=manual_distribution(prior, coarse, direction="Manual+"),
        Manual_minus=manual_distribution(prior, coarse, direction="Manual-"),
        first_Full_update=first,
        first_C_only_update=first_c,
        first_reverse=reverse,
        first_direction_ratio_upper_bound=19**0.16,
        statistical_or_training_evidence=False,
        model_calls=0,
        API_calls=0,
        GPU_calls=0,
    )


def run_experiment4(output=DEFAULT_OUTPUT):
    output = Path(output)
    module = Path(__file__).resolve()
    proof = module.parents[3] / "docs/finqa_v6_experiment4_math_20260928.md"
    paths = [module, Path(kernel.__file__), Path(kernel.__file__).with_name("protocol.py"), proof]
    sources = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    result = numerical_demonstration()
    if result["maximum_observed_pair_ratio"] > 0.8 + 1e-12:
        raise ValueError("registered arithmetic contraction control failed")
    result.update(
        design=design_metadata(),
        source_sha256=sources,
        proof_document=str(proof),
        source_commit=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=module.parent, text=True
        ).strip(),
    )
    result["id"] = "finqa_v6_experiment4:" + digest(result)
    raw = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).encode()
    manifest = dict(
        schema="finqa_v6_experiment4_pure_arithmetic.v1",
        complete=True,
        result_id=result["id"],
        files={"record.json": hashlib.sha256(raw).hexdigest()},
        source_sha256=sources,
        model_calls=0,
        API_calls=0,
        GPU_calls=0,
        no_real_trajectory_or_score_read=True,
        mathematical_proof_is_in_document=True,
        numeric_examples_are_not_proof=True,
        real_closed_loop_convergence=False,
    )
    manifest["id"] = "finqa_v6_experiment4_manifest:" + digest(manifest)
    payloads = {
        "record.json": raw,
        "manifest.json": json.dumps(
            manifest, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
        ).encode(),
    }
    if output.exists():
        if any((output / name).read_bytes() != value for name, value in payloads.items()):
            raise ValueError("immutable mathematical artifact differs; no overwrite")
    else:
        write_immutable_artifact_directory(output, payloads)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(run_experiment4(args.output), ensure_ascii=False))
