from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from finraw.qa.comparability import fact_frequency, period_index, period_key, period_label


class OperatorError(ValueError):
    pass


@dataclass(frozen=True)
class OperatorSpec:
    name: str
    input_kind: str
    output_kind: str
    difficulty_cost: float
    executor: Callable[[list[Any], dict[str, Any]], dict[str, Any]]


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise OperatorError(f"Non-numeric operator input: {value!r}") from exc


def _fact_value(fact: dict[str, Any]) -> Decimal:
    return _decimal(fact.get("normalized_value"))


def _unit_signature(facts: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    units = {fact.get("normalized_unit") for fact in facts}
    currencies = {fact.get("normalized_currency") for fact in facts}
    if len(units) != 1:
        raise OperatorError(f"Incompatible units: {sorted(str(item) for item in units)}")
    if len(currencies) != 1:
        raise OperatorError(
            f"Incompatible currencies: {sorted(str(item) for item in currencies)}"
        )
    return next(iter(units)), next(iter(currencies))


def _lookup(inputs: list[Any], params: dict[str, Any]) -> dict[str, Any]:
    if len(inputs) != 1 or not isinstance(inputs[0], dict):
        raise OperatorError("lookup requires one fact")
    fact = inputs[0]
    return {
        "value": str(_fact_value(fact)),
        "unit": fact.get("normalized_unit"),
        "currency": fact.get("normalized_currency"),
    }


def _difference(inputs: list[Any], params: dict[str, Any]) -> dict[str, Any]:
    if len(inputs) != 2 or not all(isinstance(item, dict) for item in inputs):
        raise OperatorError("difference requires two facts")
    left, right = inputs
    unit, currency = _unit_signature([left, right])
    value = _fact_value(right) - _fact_value(left)
    return {"value": str(value), "unit": unit, "currency": currency}


def _compare(inputs: list[Any], params: dict[str, Any]) -> dict[str, Any]:
    if len(inputs) != 2 or not all(isinstance(item, dict) for item in inputs):
        raise OperatorError("compare requires two facts")
    left, right = inputs
    unit, currency = _unit_signature([left, right])
    left_value = _fact_value(left)
    right_value = _fact_value(right)
    left_id = str(left.get(params.get("id_field", "entity_id")) or left.get("metric_id"))
    right_id = str(right.get(params.get("id_field", "entity_id")) or right.get("metric_id"))
    if left_value > right_value:
        winner_id, relation = left_id, "greater"
    elif right_value > left_value:
        winner_id, relation = right_id, "greater"
    else:
        winner_id, relation = None, "equal"
    return {
        "value": str(abs(left_value - right_value)),
        "difference": str(abs(left_value - right_value)),
        "winner_id": winner_id,
        "relation": relation,
        "rows": [
            {"id": left_id, "value": str(left_value)},
            {"id": right_id, "value": str(right_value)},
        ],
        "unit": unit,
        "currency": currency,
    }


def _mean(inputs: list[Any], params: dict[str, Any]) -> dict[str, Any]:
    facts = _flatten_facts(inputs)
    if not facts:
        raise OperatorError("mean requires at least one fact")
    unit, currency = _unit_signature(facts)
    value = sum((_fact_value(fact) for fact in facts), Decimal("0")) / Decimal(
        len(facts)
    )
    return {
        "value": str(value),
        "unit": unit,
        "currency": currency,
        "observation_count": len(facts),
    }


def _arg_extreme(inputs: list[Any], params: dict[str, Any]) -> dict[str, Any]:
    facts = _flatten_facts(inputs)
    if not facts:
        raise OperatorError("argmax/argmin requires at least one fact")
    unit, currency = _unit_signature(facts)
    choose = max if params.get("direction", "max") == "max" else min
    winner = choose(facts, key=_fact_value)
    frequency = str(params.get("frequency") or fact_frequency(winner))
    return {
        "value": str(_fact_value(winner)),
        "winner_id": winner.get(params.get("id_field", "entity_id")),
        "fact_id": winner.get("fact_id"),
        "period_key": period_key(winner),
        "period_index": period_index(winner, frequency),
        "frequency": frequency,
        "period": period_label(winner),
        "metric_id": winner.get("metric_id"),
        "unit": unit,
        "currency": currency,
    }


def _select_by_period(inputs: list[Any], params: dict[str, Any]) -> dict[str, Any]:
    if len(inputs) != 2 or not isinstance(inputs[0], dict):
        raise OperatorError("select_by_period requires an extrema result and a fact series")
    selection = inputs[0]
    facts = _flatten_facts([inputs[1]])
    frequency = str(selection.get("frequency") or "")
    selected_index = selection.get("period_index")
    selected_period = tuple(selection.get("period_key") or ())
    matches = [
        fact
        for fact in facts
        if (
            selected_index is not None
            and period_index(fact, frequency) == selected_index
        )
        or (
            selected_index is None
            and tuple(period_key(fact)) == selected_period
        )
    ]
    if len(matches) != 1:
        raise OperatorError(
            f"select_by_period expected one matching fact, found {len(matches)}"
        )
    fact = matches[0]
    return {
        "value": str(_fact_value(fact)),
        "period": selection.get("period") or period_label(fact),
        "result_period": selection.get("period") or period_label(fact),
        "primary_value": selection.get("value"),
        "primary_unit": selection.get("unit"),
        "primary_currency": selection.get("currency"),
        "secondary_value": str(_fact_value(fact)),
        "secondary_unit": fact.get("normalized_unit"),
        "secondary_currency": fact.get("normalized_currency"),
        "primary_fact_id": selection.get("fact_id"),
        "secondary_fact_id": fact.get("fact_id"),
        "primary_metric_id": selection.get("metric_id"),
        "secondary_metric_id": fact.get("metric_id"),
        "unit": fact.get("normalized_unit"),
        "currency": fact.get("normalized_currency"),
    }


def _rank(inputs: list[Any], params: dict[str, Any]) -> dict[str, Any]:
    facts = _flatten_facts(inputs)
    if not facts:
        raise OperatorError("rank requires at least one fact")
    unit, currency = _unit_signature(facts)
    descending = params.get("direction", "desc") == "desc"
    rows = sorted(facts, key=_fact_value, reverse=descending)
    top_k = int(params.get("top_k") or len(rows))
    return {
        "table": [
            {
                "rank": index + 1,
                "entity_id": fact.get("entity_id"),
                "value": str(_fact_value(fact)),
            }
            for index, fact in enumerate(rows[:top_k])
        ],
        "unit": unit,
        "currency": currency,
    }


def _filter(inputs: list[Any], params: dict[str, Any]) -> dict[str, Any]:
    facts = _flatten_facts(inputs)
    field = str(params.get("field") or "normalized_value")
    operator = str(params.get("comparison") or "gt")
    threshold = _decimal(params.get("value", 0))
    comparators = {
        "gt": lambda value: value > threshold,
        "gte": lambda value: value >= threshold,
        "lt": lambda value: value < threshold,
        "lte": lambda value: value <= threshold,
        "eq": lambda value: value == threshold,
    }
    if operator not in comparators:
        raise OperatorError(f"Unsupported filter comparison: {operator}")
    selected = [fact for fact in facts if comparators[operator](_decimal(fact.get(field)))]
    return {"records": selected, "count": len(selected)}


def _flatten_facts(inputs: list[Any]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for item in inputs:
        if isinstance(item, list):
            facts.extend(value for value in item if isinstance(value, dict))
        elif isinstance(item, dict) and isinstance(item.get("records"), list):
            facts.extend(value for value in item["records"] if isinstance(value, dict))
        elif isinstance(item, dict):
            facts.append(item)
    return facts


OPERATORS: dict[str, OperatorSpec] = {
    "lookup": OperatorSpec("lookup", "fact", "numeric", 0.0, _lookup),
    "difference": OperatorSpec("difference", "fact_pair", "numeric", 1.0, _difference),
    "compare": OperatorSpec("compare", "fact_pair", "comparison", 1.5, _compare),
    "mean": OperatorSpec("mean", "fact_series", "numeric", 1.5, _mean),
    "argmax": OperatorSpec("argmax", "fact_set", "entity_and_value", 2.0, _arg_extreme),
    "argmin": OperatorSpec("argmin", "fact_set", "entity_and_value", 2.0, _arg_extreme),
    "select_by_period": OperatorSpec(
        "select_by_period",
        "step_and_fact_series",
        "period_metric_lookup",
        2.0,
        _select_by_period,
    ),
    "rank": OperatorSpec("rank", "fact_set", "ranked_table", 2.5, _rank),
    "filter": OperatorSpec("filter", "fact_set", "fact_set", 1.5, _filter),
}


def operator_registry() -> dict[str, dict[str, Any]]:
    return {
        name: {
            "name": spec.name,
            "input_kind": spec.input_kind,
            "output_kind": spec.output_kind,
            "difficulty_cost": spec.difficulty_cost,
        }
        for name, spec in OPERATORS.items()
    }


def execute_operator(name: str, inputs: list[Any], params: dict[str, Any] | None = None) -> dict[str, Any]:
    if name not in OPERATORS:
        raise OperatorError(f"Unknown QA operator: {name}")
    effective_params = dict(params or {})
    if name == "argmin":
        effective_params.setdefault("direction", "min")
    return OPERATORS[name].executor(inputs, effective_params)
