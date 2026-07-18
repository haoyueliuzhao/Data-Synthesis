from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from finraw.analysis.registry import FinancialSignalSpec, signal_registry, stable_hash
from finraw.analysis.semantic_constraints import validate_signal_semantics

SIGNAL_EXECUTOR_VERSION = "1.1.0"


class SignalExecutionError(ValueError):
    pass


def signal_result_hash(
    signal_spec_id: str,
    input_fact_ids: list[str],
    payload: dict[str, Any],
    direction: str,
    strength: str,
) -> str:
    return stable_hash(
        {
            "signal_spec_id": signal_spec_id,
            "input_fact_ids": sorted(input_fact_ids),
            "payload": payload,
            "direction": direction,
            "strength": strength,
        }
    )


@dataclass(frozen=True)
class SignalExecution:
    payload: dict[str, Any]
    direction: str
    strength: str
    confidence: float
    intermediate_results: list[dict[str, Any]]


def execute_signal(
    signal_spec_id: str,
    role_facts: Mapping[str, list[dict[str, Any]]],
    *,
    target_entity_id: str | None = None,
) -> SignalExecution:
    spec = signal_registry().get(signal_spec_id)
    if spec is None:
        raise SignalExecutionError(f"Unknown financial signal spec: {signal_spec_id}")
    _validate_role_inputs(spec, role_facts)
    semantic_gate = validate_signal_semantics(
        spec, role_facts, target_entity_id=target_entity_id
    )
    if not semantic_gate["passed"]:
        raise SignalExecutionError(
            "Signal semantic gate failed: " + ", ".join(semantic_gate["errors"])
        )
    if spec.signal_type == "period_growth":
        return _period_growth(spec, role_facts)
    if spec.signal_type == "trend_consistency":
        return _trend_consistency(spec, role_facts)
    if spec.signal_type == "earnings_cash_divergence":
        return _earnings_cash_divergence(spec, role_facts)
    if spec.signal_type in {"margin_change", "asset_efficiency_change"}:
        return _ratio_change(spec, role_facts)
    if spec.signal_spec_id == "peer_growth_percentile_v1":
        return _peer_growth(spec, role_facts, target_entity_id)
    if spec.signal_spec_id in {
        "peer_margin_percentile_v1",
        "peer_leverage_percentile_v1",
    }:
        return _peer_ratio(spec, role_facts, target_entity_id)
    raise SignalExecutionError(f"No executor registered for {signal_spec_id}")


def _validate_role_inputs(
    spec: FinancialSignalSpec, role_facts: Mapping[str, list[dict[str, Any]]]
) -> None:
    missing = sorted(set(spec.input_roles) - set(role_facts))
    if missing:
        raise SignalExecutionError(f"Missing signal input roles: {missing}")
    all_rows = [row for values in role_facts.values() for row in values]
    if not all_rows:
        raise SignalExecutionError("Signal has no input facts")
    if any(_truthy(row.get("is_forecast")) for row in all_rows):
        raise SignalExecutionError("Forecast facts are not allowed in analysis signals")
    if any(not _truthy(row.get("graph_ready")) for row in all_rows):
        raise SignalExecutionError("All signal facts must be graph-ready")
    for role, rows in role_facts.items():
        if not rows:
            raise SignalExecutionError(f"Signal role {role} is empty")
        if len({str(row.get("fact_id")) for row in rows}) != len(rows):
            raise SignalExecutionError(f"Signal role {role} contains duplicate facts")


def _period_growth(
    spec: FinancialSignalSpec, role_facts: Mapping[str, list[dict[str, Any]]]
) -> SignalExecution:
    rows = _ordered_series(role_facts["series"])
    _require_contiguous(rows, spec.required_periods)
    first = _value(rows[0])
    last = _value(rows[-1])
    if first == 0:
        raise SignalExecutionError("Growth denominator is zero")
    growth = ((last - first) / abs(first)) * Decimal("100")
    direction, strength = _signed_direction_strength(growth, spec)
    payload = {
        "metric_id": rows[0].get("metric_id"),
        "first_period": _year(rows[0]),
        "last_period": _year(rows[-1]),
        "first_value": str(first),
        "last_value": str(last),
        "growth_pct": str(growth),
        "unit": rows[0].get("normalized_unit"),
        "currency": rows[0].get("normalized_currency"),
    }
    return SignalExecution(
        payload,
        direction,
        strength,
        _confidence(rows),
        [{"operator": "first_last_growth", "output": payload}],
    )


def _trend_consistency(
    spec: FinancialSignalSpec, role_facts: Mapping[str, list[dict[str, Any]]]
) -> SignalExecution:
    rows = _ordered_series(role_facts["series"])
    _require_contiguous(rows, spec.required_periods)
    changes = [_value(right) - _value(left) for left, right in zip(rows, rows[1:])]
    increases = sum(value > 0 for value in changes)
    decreases = sum(value < 0 for value in changes)
    steps = len(changes)
    consistency = Decimal(increases - decreases) / Decimal(steps)
    direction = "positive" if consistency > 0 else "negative" if consistency < 0 else "neutral"
    strength = "strong" if abs(consistency) == 1 else "moderate" if consistency else "weak"
    payload = {
        "metric_id": rows[0].get("metric_id"),
        "increase_count": increases,
        "decrease_count": decreases,
        "observation_count": len(rows),
        "consistency": str(consistency),
    }
    return SignalExecution(
        payload,
        direction,
        strength,
        _confidence(rows),
        [{"operator": "direction_consistency", "changes": [str(value) for value in changes], "output": payload}],
    )


def _earnings_cash_divergence(
    spec: FinancialSignalSpec, role_facts: Mapping[str, list[dict[str, Any]]]
) -> SignalExecution:
    profit = _ordered_series(role_facts["profit_series"])
    cash = _ordered_series(role_facts["cash_series"])
    _require_aligned_series(profit, cash, spec.required_periods)
    profit_growth = _growth(profit)
    cash_growth = _growth(cash)
    spread = profit_growth - cash_growth
    negative_limit = _decimal(spec.direction_policy["negative_spread_gt"])
    positive_limit = _decimal(spec.direction_policy["positive_spread_lt"])
    direction = "negative" if spread > negative_limit else "positive" if spread < positive_limit else "neutral"
    strength = _absolute_strength(spread, spec)
    payload = {
        "first_period": _year(profit[0]),
        "last_period": _year(profit[-1]),
        "profit_growth_pct": str(profit_growth),
        "cash_growth_pct": str(cash_growth),
        "spread_pct": str(spread),
    }
    rows = profit + cash
    return SignalExecution(
        payload,
        direction,
        strength,
        _confidence(rows),
        [{"operator": "growth_spread", "output": payload}],
    )


def _ratio_change(
    spec: FinancialSignalSpec, role_facts: Mapping[str, list[dict[str, Any]]]
) -> SignalExecution:
    role_names = list(spec.input_roles)
    numerator = _ordered_series(role_facts[role_names[0]])
    denominator = _ordered_series(role_facts[role_names[1]])
    _require_aligned_series(numerator, denominator, spec.required_periods)
    first_ratio = _ratio(_value(numerator[0]), _value(denominator[0]))
    last_ratio = _ratio(_value(numerator[-1]), _value(denominator[-1]))
    change = last_ratio - first_ratio
    direction, strength = _signed_direction_strength(change, spec)
    payload = {
        "first_period": _year(numerator[0]),
        "last_period": _year(numerator[-1]),
        "first_ratio_pct": str(first_ratio),
        "last_ratio_pct": str(last_ratio),
        "change_pp": str(change),
    }
    rows = numerator + denominator
    return SignalExecution(
        payload,
        direction,
        strength,
        _confidence(rows),
        [{"operator": "ratio_change", "output": payload}],
    )


def _peer_growth(
    spec: FinancialSignalSpec,
    role_facts: Mapping[str, list[dict[str, Any]]],
    target_entity_id: str | None,
) -> SignalExecution:
    current = _unique_by_entity(role_facts["current"])
    previous = _unique_by_entity(role_facts["previous"])
    common = sorted(set(current) & set(previous))
    values = {entity_id: _growth([previous[entity_id], current[entity_id]]) for entity_id in common}
    return _peer_position(spec, values, role_facts, target_entity_id, adverse_high=False)


def _peer_ratio(
    spec: FinancialSignalSpec,
    role_facts: Mapping[str, list[dict[str, Any]]],
    target_entity_id: str | None,
) -> SignalExecution:
    role_names = list(spec.input_roles)
    numerator = _unique_by_entity(role_facts[role_names[0]])
    denominator = _unique_by_entity(role_facts[role_names[1]])
    common = sorted(set(numerator) & set(denominator))
    values = {
        entity_id: _ratio(_value(numerator[entity_id]), _value(denominator[entity_id]))
        for entity_id in common
    }
    adverse_high = spec.signal_spec_id == "peer_leverage_percentile_v1"
    return _peer_position(spec, values, role_facts, target_entity_id, adverse_high=adverse_high)


def _peer_position(
    spec: FinancialSignalSpec,
    values: dict[str, Decimal],
    role_facts: Mapping[str, list[dict[str, Any]]],
    target_entity_id: str | None,
    *,
    adverse_high: bool,
) -> SignalExecution:
    if not target_entity_id or target_entity_id not in values:
        raise SignalExecutionError("Target entity is absent from the complete peer scope")
    if len(values) < 2:
        raise SignalExecutionError("Peer percentile requires at least two entities")
    target = values[target_entity_id]
    below = sum(value < target for value in values.values())
    equal = sum(value == target for value in values.values())
    percentile = (Decimal(below) + (Decimal(equal - 1) / Decimal("2"))) / Decimal(len(values) - 1)
    high = percentile >= Decimal("0.67")
    low = percentile <= Decimal("0.33")
    if adverse_high:
        direction = "negative" if high else "positive" if low else "neutral"
    else:
        direction = "positive" if high else "negative" if low else "neutral"
    tail = min(percentile, Decimal("1") - percentile)
    strength = "strong" if tail <= Decimal("0.20") else "moderate" if tail <= Decimal("0.33") else "weak"
    payload = {
        "target_entity_id": target_entity_id,
        "target_value": str(target),
        "percentile": str(percentile),
        "scope_size": len(values),
        "scope_values": {key: str(value) for key, value in sorted(values.items())},
        "unit": "percent",
    }
    rows = [row for group in role_facts.values() for row in group]
    return SignalExecution(
        payload,
        direction,
        strength,
        _confidence(rows),
        [{"operator": spec.operator_dag[0]["operator"], "output": payload}],
    )


def _signed_direction_strength(
    value: Decimal, spec: FinancialSignalSpec
) -> tuple[str, str]:
    positive = _decimal(spec.direction_policy.get("positive_gt", 0))
    negative = _decimal(spec.direction_policy.get("negative_lt", 0))
    direction = "positive" if value > positive else "negative" if value < negative else "neutral"
    return direction, _absolute_strength(value, spec)


def _absolute_strength(value: Decimal, spec: FinancialSignalSpec) -> str:
    absolute = abs(value)
    strong = _decimal(spec.strength_policy.get("strong_abs", 15))
    moderate = _decimal(spec.strength_policy.get("moderate_abs", 5))
    return "strong" if absolute >= strong else "moderate" if absolute >= moderate else "weak"


def _ordered_series(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(rows, key=lambda row: (_year(row), str(row.get("fact_id"))))
    years = [_year(row) for row in ordered]
    if len(years) != len(set(years)):
        raise SignalExecutionError("Series contains multiple facts for the same period")
    definitions = {str(row.get("source_definition_id") or "") for row in ordered}
    if len(definitions) != 1 or "" in definitions:
        raise SignalExecutionError("Series source definition is missing or changes within the window")
    return ordered


def _require_contiguous(rows: list[dict[str, Any]], minimum: int) -> None:
    years = [_year(row) for row in rows]
    if len(rows) < minimum or any(right - left != 1 for left, right in zip(years, years[1:])):
        raise SignalExecutionError("Signal requires a complete contiguous annual window")


def _require_aligned_series(
    left: list[dict[str, Any]], right: list[dict[str, Any]], minimum: int
) -> None:
    _require_contiguous(left, minimum)
    _require_contiguous(right, minimum)
    if [_year(row) for row in left] != [_year(row) for row in right]:
        raise SignalExecutionError("Signal series do not cover the same fiscal periods")


def _unique_by_entity(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        entity_id = str(row.get("entity_id") or "")
        if not entity_id or entity_id in result:
            raise SignalExecutionError("Peer signal requires one fact per entity and role")
        result[entity_id] = row
    return result


def _growth(rows: list[dict[str, Any]]) -> Decimal:
    ordered = sorted(rows, key=lambda row: (_year(row), str(row.get("fact_id"))))
    first = _value(ordered[0])
    if first == 0:
        raise SignalExecutionError("Growth denominator is zero")
    return ((_value(ordered[-1]) - first) / abs(first)) * Decimal("100")


def _ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == 0:
        raise SignalExecutionError("Ratio denominator is zero")
    return (numerator / denominator) * Decimal("100")


def _year(row: Mapping[str, Any]) -> int:
    value = row.get("fiscal_year") or row.get("calendar_year")
    if value is None:
        raise SignalExecutionError("Fact is missing an annual period")
    return int(value)


def _value(row: Mapping[str, Any]) -> Decimal:
    return _decimal(row.get("normalized_value"))


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise SignalExecutionError(f"Invalid numeric signal input: {value!r}") from exc


def _confidence(rows: list[dict[str, Any]]) -> float:
    values = [float(row.get("confidence_score") or 0.8) for row in rows]
    return round(min(values, default=0.0), 6)


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)
