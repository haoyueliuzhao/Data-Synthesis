from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Callable


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
    return {
        "value": str(_fact_value(winner)),
        "winner_id": winner.get(params.get("id_field", "entity_id")),
        "fact_id": winner.get("fact_id"),
        "unit": unit,
        "currency": currency,
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
