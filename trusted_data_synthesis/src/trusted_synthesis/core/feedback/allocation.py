from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Mapping

from trusted_synthesis.hashing import canonical_hash

from .schema import (
    AllocationCell,
    FeedbackExposure,
    FeedbackRoute,
    FeedbackSignal,
    PatternClauseFailure,
    RefinementAllocation,
)


def aggregate_pattern_clause_failures(
    exposures: Iterable[FeedbackExposure],
    signals: Iterable[FeedbackSignal],
) -> tuple[PatternClauseFailure, ...]:
    exposure_items = tuple(exposures)
    signal_items = tuple(
        item for item in signals if item.route == FeedbackRoute.AGENT_CAPABILITY_GAP
    )
    exposure_groups: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    domains: dict[tuple[str, str], set[str]] = defaultdict(set)
    for exposure in exposure_items:
        key = (exposure.pattern_id, exposure.failure_family)
        exposure_groups[key].add((exposure.task_id, exposure.domain))
        domains[key].add(exposure.domain)
    signal_groups: dict[tuple[str, str], dict[tuple[str, str], float]] = defaultdict(dict)
    for signal in signal_items:
        key = (signal.pattern_id, signal.failure_family)
        identity = (signal.task_id, signal.domain)
        signal_groups[key][identity] = max(
            signal_groups[key].get(identity, 0.0),
            signal.weight,
        )
    unknown_cells = set(signal_groups) - set(exposure_groups)
    if unknown_cells:
        raise ValueError(
            f"capability feedback lacks a matching exposure: {sorted(unknown_cells)}"
        )
    output = []
    for pattern_id, failure_family in sorted(exposure_groups):
        key = (pattern_id, failure_family)
        observed = signal_groups.get(key, {})
        exposure_count = len(exposure_groups[key])
        weighted_sum = sum(observed.values())
        cell_identity = {
            "pattern_id": pattern_id,
            "failure_family": failure_family,
        }
        output.append(
            PatternClauseFailure(
                cell_id=canonical_hash(cell_identity, prefix="pattern_clause_cell:"),
                pattern_id=pattern_id,
                failure_family=failure_family,
                exposure_count=exposure_count,
                root_failure_count=len(observed),
                weighted_root_failure_sum=weighted_sum,
                weighted_root_failure_rate=weighted_sum / exposure_count,
                contributing_domains=tuple(sorted(domains[key])),
            )
        )
    return tuple(output)


def allocate_refinement_budget(
    failures: tuple[PatternClauseFailure, ...],
    *,
    total_budget: int,
    lambda_value: float,
    alpha: float = 1.0,
    epsilon: float = 0.01,
    base_weights: Mapping[str, float] | None = None,
    capability_signal_count: int = 0,
) -> RefinementAllocation:
    if not failures:
        raise ValueError("refinement allocation requires at least one exposed cell")
    if total_budget < 1:
        raise ValueError("refinement budget must be positive")
    if not 0 <= lambda_value <= 1:
        raise ValueError("lambda_value must be between zero and one")
    if alpha <= 0 or epsilon <= 0:
        raise ValueError("alpha and epsilon must be positive")
    observed_ids = {item.cell_id for item in failures}
    if base_weights is not None and set(base_weights) != observed_ids:
        raise ValueError("base weights must cover every exposed cell exactly")
    raw_base = {
        item.cell_id: (1.0 if base_weights is None else float(base_weights[item.cell_id]))
        for item in failures
    }
    if any(value < 0 for value in raw_base.values()) or sum(raw_base.values()) <= 0:
        raise ValueError("base weights must be non-negative with positive total mass")
    base_total = sum(raw_base.values())
    base_probability = {key: value / base_total for key, value in raw_base.items()}
    feedback_mass = {
        item.cell_id: (item.weighted_root_failure_rate + epsilon) ** alpha
        for item in failures
    }
    feedback_total = sum(feedback_mass.values())
    feedback_probability = {
        key: value / feedback_total for key, value in feedback_mass.items()
    }
    final_probability = {
        key: (1 - lambda_value) * base_probability[key]
        + lambda_value * feedback_probability[key]
        for key in sorted(base_probability)
    }
    allocated = _largest_remainder(final_probability, total_budget)
    rows = tuple(
        AllocationCell(
            cell_id=item.cell_id,
            pattern_id=item.pattern_id,
            failure_family=item.failure_family,
            base_probability=base_probability[item.cell_id],
            feedback_probability=feedback_probability[item.cell_id],
            final_probability=final_probability[item.cell_id],
            allocated_count=allocated[item.cell_id],
        )
        for item in failures
    )
    identity = {
        "lambda_value": lambda_value,
        "alpha": alpha,
        "epsilon": epsilon,
        "total_budget": total_budget,
        "cells": rows,
        "capability_signal_count": capability_signal_count,
    }
    return RefinementAllocation(
        allocation_id=canonical_hash(identity, prefix="refinement_allocation:"),
        lambda_value=lambda_value,
        alpha=alpha,
        epsilon=epsilon,
        total_budget=total_budget,
        cells=rows,
        capability_signal_count=capability_signal_count,
    )


def _largest_remainder(probabilities: Mapping[str, float], budget: int) -> dict[str, int]:
    raw = {key: probabilities[key] * budget for key in sorted(probabilities)}
    allocated = {key: math.floor(value) for key, value in raw.items()}
    remainder = budget - sum(allocated.values())
    order = sorted(raw, key=lambda key: (-(raw[key] - allocated[key]), key))
    for key in order[:remainder]:
        allocated[key] += 1
    return allocated
