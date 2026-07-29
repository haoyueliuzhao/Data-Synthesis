from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import Literal

from trusted_synthesis.core.feedback import FeedbackRoute
from trusted_synthesis.hashing import canonical_hash

from .aggregate import make_synthesis_cell
from .schema import (
    CellFeedbackStatistics,
    ClauseFeedback,
    PolicyUpdateResult,
    SynthesisCell,
    SynthesisPolicy,
    policy_update_id,
    synthesis_policy_id,
)


def update_synthesis_policy(
    prior_policy: SynthesisPolicy,
    statistics: Iterable[CellFeedbackStatistics],
    feedback: Iterable[ClauseFeedback],
    *,
    eta: float,
    beta: float,
    gamma: float,
    total_budget: int,
    calibration_manifest_hash: str,
    ablation_id: str = "full_ccgr",
    binding_tightening_threshold: float = 0.25,
    enable_binding_tightening: bool = True,
    require_calibrated_feedback: bool = True,
    utility_overrides: Mapping[str, float] | None = None,
    utility_mode: Literal["feedback_objective", "random_control"] = ("feedback_objective"),
    conditioning_groups: Mapping[str, str] | None = None,
    fixed_group_weights: Mapping[str, float] | None = None,
) -> PolicyUpdateResult:
    """Apply the closed-form exponentiated CCGR policy update."""

    if eta < 0 or beta < 0 or gamma < 0:
        raise ValueError("CCGR eta, beta, and gamma must be non-negative")
    if total_budget < 1:
        raise ValueError("CCGR total budget must be positive")
    if not 0 <= binding_tightening_threshold:
        raise ValueError("binding tightening threshold must be non-negative")
    if utility_mode not in {"feedback_objective", "random_control"}:
        raise ValueError("unknown CCGR utility mode")
    stats = tuple(sorted(statistics, key=lambda item: item.cell_id))
    feedback_items = tuple(sorted(feedback, key=lambda item: item.feedback_id))
    prior_ids = {cell.cell_id for cell in prior_policy.cells}
    if {item.cell_id for item in stats} != prior_ids:
        raise ValueError("CCGR statistics must cover the prior policy exactly")
    utilities = (
        dict(utility_overrides)
        if utility_overrides is not None
        else {
            item.cell_id: (
                item.capability_gap_demand
                - beta * item.synthesis_defect_risk
                + gamma * item.coverage_gap
            )
            for item in stats
        }
    )
    if set(utilities) != prior_ids:
        raise ValueError("CCGR utility overrides must cover the prior policy exactly")
    (
        conditioning_mode,
        resolved_groups,
        resolved_group_weights,
    ) = _resolve_conditioning_contract(
        prior_policy.probabilities,
        conditioning_groups,
        fixed_group_weights,
    )
    updated_probabilities = _exponentiated_distribution(
        prior_policy.probabilities,
        utilities,
        eta,
        conditioning_groups=resolved_groups,
        fixed_group_weights=resolved_group_weights,
    )
    activated, unresolved = _select_binding_tightening(
        prior_policy.cells,
        stats,
        feedback_items,
        threshold=binding_tightening_threshold,
        enabled=enable_binding_tightening,
    )
    next_cells, transitions = _transition_cells(prior_policy.cells, activated)
    next_probabilities = _transition_distribution(updated_probabilities, transitions)
    next_targets = _transition_distribution(
        prior_policy.target_probabilities,
        transitions,
    )
    next_conditioning_groups = (
        {transitions[cell_id]: resolved_groups[cell_id] for cell_id in sorted(resolved_groups)}
        if resolved_groups
        else {}
    )
    provisional_policy = SynthesisPolicy.model_construct(
        policy_id="pending",
        round_index=prior_policy.round_index + 1,
        label=f"{prior_policy.label}:{ablation_id}",
        cells=next_cells,
        probabilities=next_probabilities,
        target_probabilities=next_targets,
        source_policy_id=prior_policy.policy_id,
    )
    next_policy = SynthesisPolicy(
        policy_id=synthesis_policy_id(provisional_policy),
        round_index=prior_policy.round_index + 1,
        label=f"{prior_policy.label}:{ablation_id}",
        cells=next_cells,
        probabilities=next_probabilities,
        target_probabilities=next_targets,
        source_policy_id=prior_policy.policy_id,
    )
    if next_conditioning_groups:
        allocations, allocated_group_counts = _conditional_largest_remainder_allocation(
            next_policy.probabilities,
            total_budget,
            next_conditioning_groups,
            resolved_group_weights,
        )
    else:
        allocations = _largest_remainder_allocation(
            next_policy.probabilities,
            total_budget,
        )
        allocated_group_counts = {}
    calibrated_directional = tuple(
        item
        for item in feedback_items
        if item.route != FeedbackRoute.INTERFACE_FAILURE and item.calibration_reliability > 0
    )
    failures = (
        ("no_calibrated_directional_feedback",)
        if require_calibrated_feedback and not calibrated_directional
        else ()
    )
    prior_entropy = _entropy(prior_policy.probabilities)
    next_on_prior = {
        prior_id: next_policy.probabilities[next_id] for prior_id, next_id in transitions.items()
    }
    feedback_manifest_hash = canonical_hash(
        tuple(item.feedback_id for item in feedback_items),
        prefix="ccgr_feedback_manifest:",
    )
    cell_utilities = dict(sorted(utilities.items()))
    cell_transition_map = dict(sorted(transitions.items()))
    allocated_counts = dict(sorted(allocations.items()))
    activated_constraints = dict(sorted(activated.items()))
    kl_divergence = _kl_divergence(next_on_prior, prior_policy.probabilities)
    total_variation_distance = _total_variation(
        next_on_prior,
        prior_policy.probabilities,
    )
    next_entropy = _entropy(next_policy.probabilities)
    expected_before = sum(
        prior_policy.probabilities[cell_id] * utilities[cell_id] for cell_id in prior_ids
    )
    expected_after = sum(next_on_prior[cell_id] * utilities[cell_id] for cell_id in prior_ids)
    status: Literal["passed", "blocked"] = "blocked" if failures else "passed"
    provisional = PolicyUpdateResult.model_construct(
        update_id="pending",
        ablation_id=ablation_id,
        prior_policy=prior_policy,
        next_policy=next_policy,
        statistics=stats,
        cell_utilities=cell_utilities,
        cell_transition_map=cell_transition_map,
        allocated_counts=allocated_counts,
        conditioning_mode=conditioning_mode,
        conditioning_groups=dict(sorted(next_conditioning_groups.items())),
        fixed_group_weights=dict(sorted(resolved_group_weights.items())),
        allocated_group_counts=dict(sorted(allocated_group_counts.items())),
        activated_binding_constraints=activated_constraints,
        tightening_without_declared_option=unresolved,
        eta=eta,
        beta=beta,
        gamma=gamma,
        total_budget=total_budget,
        calibration_manifest_hash=calibration_manifest_hash,
        feedback_manifest_hash=feedback_manifest_hash,
        utility_mode=utility_mode,
        kl_divergence=kl_divergence,
        total_variation_distance=total_variation_distance,
        prior_entropy=prior_entropy,
        next_entropy=next_entropy,
        prior_effective_cell_count=math.exp(prior_entropy),
        next_effective_cell_count=math.exp(next_entropy),
        expected_utility_before=expected_before,
        expected_utility_after=expected_after,
        status=status,
        failures=failures,
    )
    return PolicyUpdateResult(
        update_id=policy_update_id(provisional),
        ablation_id=ablation_id,
        prior_policy=prior_policy,
        next_policy=next_policy,
        statistics=stats,
        cell_utilities=cell_utilities,
        cell_transition_map=cell_transition_map,
        allocated_counts=allocated_counts,
        conditioning_mode=conditioning_mode,
        conditioning_groups=dict(sorted(next_conditioning_groups.items())),
        fixed_group_weights=dict(sorted(resolved_group_weights.items())),
        allocated_group_counts=dict(sorted(allocated_group_counts.items())),
        activated_binding_constraints=activated_constraints,
        tightening_without_declared_option=unresolved,
        eta=eta,
        beta=beta,
        gamma=gamma,
        total_budget=total_budget,
        calibration_manifest_hash=calibration_manifest_hash,
        feedback_manifest_hash=feedback_manifest_hash,
        utility_mode=utility_mode,
        kl_divergence=kl_divergence,
        total_variation_distance=total_variation_distance,
        prior_entropy=prior_entropy,
        next_entropy=next_entropy,
        prior_effective_cell_count=math.exp(prior_entropy),
        next_effective_cell_count=math.exp(next_entropy),
        expected_utility_before=expected_before,
        expected_utility_after=expected_after,
        status=status,
        failures=failures,
    )


def random_same_shift_update(
    prior_policy: SynthesisPolicy,
    statistics: Iterable[CellFeedbackStatistics],
    *,
    reference_update: PolicyUpdateResult,
    total_budget: int,
    calibration_manifest_hash: str,
    random_seed: int,
) -> PolicyUpdateResult:
    """Deterministic random baseline matched to Full CCGR's TV distance."""

    stats = tuple(statistics)
    random_values = {
        cell.cell_id: _stable_random_value(cell.cell_id, random_seed) for cell in prior_policy.cells
    }
    if reference_update.conditioning_mode == "fixed_group_marginals":
        prior_groups = {
            prior_id: reference_update.conditioning_groups[
                reference_update.cell_transition_map[prior_id]
            ]
            for prior_id in prior_policy.probabilities
        }
        centered: dict[str, float] = {}
        for group in sorted(set(prior_groups.values())):
            members = tuple(
                cell_id for cell_id in prior_policy.probabilities if prior_groups[cell_id] == group
            )
            group_mass = sum(prior_policy.probabilities[cell_id] for cell_id in members)
            mean = (
                sum(
                    prior_policy.probabilities[cell_id] * random_values[cell_id]
                    for cell_id in members
                )
                / group_mass
            )
            centered.update({cell_id: random_values[cell_id] - mean for cell_id in members})
        fixed_weights = reference_update.fixed_group_weights
    else:
        weighted_mean = sum(
            prior_policy.probabilities[cell_id] * value for cell_id, value in random_values.items()
        )
        centered = {cell_id: value - weighted_mean for cell_id, value in random_values.items()}
        prior_groups = {}
        fixed_weights = {}
    target_tv = reference_update.total_variation_distance
    eta = _eta_for_tv(
        prior_policy.probabilities,
        centered,
        target_tv,
        conditioning_groups=prior_groups,
        fixed_group_weights=fixed_weights,
    )
    return update_synthesis_policy(
        prior_policy,
        stats,
        (),
        eta=eta,
        beta=0,
        gamma=0,
        total_budget=total_budget,
        calibration_manifest_hash=calibration_manifest_hash,
        ablation_id="random_same_shift",
        enable_binding_tightening=False,
        require_calibrated_feedback=False,
        utility_overrides=centered,
        utility_mode="random_control",
        conditioning_groups=prior_groups or None,
        fixed_group_weights=fixed_weights or None,
    )


def _select_binding_tightening(
    cells: tuple[SynthesisCell, ...],
    statistics: tuple[CellFeedbackStatistics, ...],
    feedback: tuple[ClauseFeedback, ...],
    *,
    threshold: float,
    enabled: bool,
) -> tuple[dict[str, tuple[str, ...]], tuple[str, ...]]:
    if not enabled:
        return {}, ()
    cells_by_id = {cell.cell_id: cell for cell in cells}
    stats_by_id = {item.cell_id: item for item in statistics}
    activated: dict[str, set[str]] = {}
    unresolved: set[str] = set()
    for item in feedback:
        if item.route != FeedbackRoute.UPSTREAM_DATA_DEFECT:
            continue
        if item.calibrated_weight <= 0:
            continue
        stats = stats_by_id[item.cell_id]
        if stats.synthesis_defect_risk < threshold:
            continue
        cell = cells_by_id[item.cell_id]
        options = cell.declared_tightening_options.get(item.clause_kind)
        if options is None:
            options = cell.declared_tightening_options.get(f"failure_family:{item.failure_family}")
        if not options:
            unresolved.add(item.clause_kind)
            continue
        pending = set(options) - set(cell.active_binding_constraints)
        if pending:
            activated.setdefault(cell.cell_id, set()).update(pending)
    return (
        {key: tuple(sorted(values)) for key, values in sorted(activated.items())},
        tuple(sorted(unresolved)),
    )


def _transition_cells(
    cells: tuple[SynthesisCell, ...],
    activated: Mapping[str, tuple[str, ...]],
) -> tuple[tuple[SynthesisCell, ...], dict[str, str]]:
    next_by_id: dict[str, SynthesisCell] = {}
    transitions: dict[str, str] = {}
    for cell in cells:
        additions = activated.get(cell.cell_id, ())
        if additions:
            next_cell = make_synthesis_cell(
                pattern_id=cell.pattern_id,
                binding_stratum_id=cell.binding_stratum_id,
                difficulty_bucket=cell.difficulty_bucket,
                distractor_profile_id=cell.distractor_profile_id,
                declared_tightening_options=cell.declared_tightening_options,
                active_binding_constraints=(
                    *cell.active_binding_constraints,
                    *additions,
                ),
            )
        else:
            next_cell = cell
        existing = next_by_id.get(next_cell.cell_id)
        if existing is not None:
            raise ValueError("cell tightening cannot merge distinct prior cells")
        next_by_id[next_cell.cell_id] = next_cell
        transitions[cell.cell_id] = next_cell.cell_id
    return tuple(next_by_id[key] for key in sorted(next_by_id)), transitions


def _transition_distribution(
    values: Mapping[str, float],
    transitions: Mapping[str, str],
) -> dict[str, float]:
    result: dict[str, float] = {}
    for source_id, value in values.items():
        target_id = transitions[source_id]
        result[target_id] = result.get(target_id, 0.0) + value
    return dict(sorted(result.items()))


def _resolve_conditioning_contract(
    prior: Mapping[str, float],
    groups: Mapping[str, str] | None,
    fixed_weights: Mapping[str, float] | None,
) -> tuple[
    Literal["global", "fixed_group_marginals"],
    dict[str, str],
    dict[str, float],
]:
    if groups is None and fixed_weights is None:
        return "global", {}, {}
    if groups is None or fixed_weights is None:
        raise ValueError("conditioning groups and fixed weights must be supplied together")
    if set(groups) != set(prior):
        raise ValueError("conditioning groups must cover every prior-policy Cell")
    observed_groups = set(groups.values())
    if set(fixed_weights) != observed_groups:
        raise ValueError("fixed group weights must cover the represented groups exactly")
    if any(value <= 0 for value in fixed_weights.values()):
        raise ValueError("fixed group weights must be positive")
    if not math.isclose(sum(fixed_weights.values()), 1.0, abs_tol=1e-9):
        raise ValueError("fixed group weights must sum to one")
    observed_mass = {
        group: sum(prior[cell_id] for cell_id in prior if groups[cell_id] == group)
        for group in observed_groups
    }
    if any(
        not math.isclose(observed_mass[group], fixed_weights[group], abs_tol=1e-9)
        for group in observed_groups
    ):
        raise ValueError("prior policy does not satisfy the fixed group marginals")
    return (
        "fixed_group_marginals",
        dict(sorted(groups.items())),
        dict(sorted(fixed_weights.items())),
    )


def _conditional_largest_remainder_allocation(
    probabilities: Mapping[str, float],
    total_budget: int,
    groups: Mapping[str, str],
    fixed_weights: Mapping[str, float],
) -> tuple[dict[str, int], dict[str, int]]:
    group_counts = _largest_remainder_allocation(fixed_weights, total_budget)
    allocated = {cell_id: 0 for cell_id in probabilities}
    for group, group_budget in sorted(group_counts.items()):
        members = {
            cell_id: probabilities[cell_id] for cell_id in probabilities if groups[cell_id] == group
        }
        group_mass = sum(members.values())
        conditional = {cell_id: value / group_mass for cell_id, value in members.items()}
        allocated.update(_largest_remainder_allocation(conditional, group_budget))
    return dict(sorted(allocated.items())), dict(sorted(group_counts.items()))


def _exponentiated_distribution(
    prior: Mapping[str, float],
    utilities: Mapping[str, float],
    eta: float,
    *,
    conditioning_groups: Mapping[str, str] | None = None,
    fixed_group_weights: Mapping[str, float] | None = None,
) -> dict[str, float]:
    if not conditioning_groups:
        log_weights = {key: math.log(value) + eta * utilities[key] for key, value in prior.items()}
        maximum = max(log_weights.values())
        weights = {key: math.exp(value - maximum) for key, value in log_weights.items()}
        total = sum(weights.values())
        return {key: weights[key] / total for key in sorted(weights)}

    if fixed_group_weights is None:
        raise ValueError("conditional exponentiation requires fixed group weights")
    output: dict[str, float] = {}
    for group, group_weight in sorted(fixed_group_weights.items()):
        members = tuple(cell_id for cell_id in prior if conditioning_groups[cell_id] == group)
        log_weights = {
            cell_id: math.log(prior[cell_id]) + eta * utilities[cell_id] for cell_id in members
        }
        maximum = max(log_weights.values())
        weights = {cell_id: math.exp(value - maximum) for cell_id, value in log_weights.items()}
        total = sum(weights.values())
        output.update({cell_id: group_weight * weights[cell_id] / total for cell_id in members})
    return dict(sorted(output.items()))


def _largest_remainder_allocation(
    probabilities: Mapping[str, float],
    total_budget: int,
) -> dict[str, int]:
    raw = {key: value * total_budget for key, value in probabilities.items()}
    allocated = {key: math.floor(value) for key, value in raw.items()}
    remaining = total_budget - sum(allocated.values())
    priority = sorted(
        raw,
        key=lambda key: (-(raw[key] - allocated[key]), key),
    )
    for key in priority[:remaining]:
        allocated[key] += 1
    return allocated


def _eta_for_tv(
    prior: Mapping[str, float],
    utilities: Mapping[str, float],
    target_tv: float,
    *,
    conditioning_groups: Mapping[str, str] | None = None,
    fixed_group_weights: Mapping[str, float] | None = None,
) -> float:
    if target_tv <= 1e-12 or len(prior) == 1:
        return 0.0
    low = 0.0
    high = 1.0
    while high < 4096:
        candidate = _exponentiated_distribution(
            prior,
            utilities,
            high,
            conditioning_groups=conditioning_groups,
            fixed_group_weights=fixed_group_weights,
        )
        if _total_variation(candidate, prior) >= target_tv:
            break
        high *= 2
    for _ in range(80):
        middle = (low + high) / 2
        candidate = _exponentiated_distribution(
            prior,
            utilities,
            middle,
            conditioning_groups=conditioning_groups,
            fixed_group_weights=fixed_group_weights,
        )
        if _total_variation(candidate, prior) < target_tv:
            low = middle
        else:
            high = middle
    return high


def _stable_random_value(cell_id: str, seed: int) -> float:
    digest = canonical_hash(
        {"cell_id": cell_id, "seed": seed},
        prefix="ccgr_random_control:",
    ).split(":", 1)[1]
    return int(digest[:16], 16) / float(16**16 - 1)


def _kl_divergence(
    current: Mapping[str, float],
    prior: Mapping[str, float],
) -> float:
    value = sum(current[key] * math.log(current[key] / prior[key]) for key in prior)
    if value >= 0:
        return value
    if value >= -1e-12:
        return 0.0
    raise ValueError(f"KL divergence is materially negative: {value}")


def _total_variation(
    left: Mapping[str, float],
    right: Mapping[str, float],
) -> float:
    return 0.5 * sum(abs(left[key] - right[key]) for key in left)


def _entropy(values: Mapping[str, float]) -> float:
    return -sum(value * math.log(value) for value in values.values() if value > 0)
