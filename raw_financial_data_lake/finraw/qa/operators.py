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


def _growth_by_entity(inputs: list[Any], params: dict[str, Any]) -> dict[str, Any]:
    if len(inputs) != 2:
        raise OperatorError("growth_by_entity requires current and previous fact sets")
    current = _unique_by_entity(_flatten_facts([inputs[0]]), "current")
    previous = _unique_by_entity(_flatten_facts([inputs[1]]), "previous")
    records = []
    for entity_id in sorted(set(current) & set(previous)):
        current_fact = current[entity_id]
        previous_fact = previous[entity_id]
        _unit_signature([current_fact, previous_fact])
        prior = _fact_value(previous_fact)
        if prior == 0:
            continue
        value = ((_fact_value(current_fact) - prior) / abs(prior)) * Decimal("100")
        records.append(
            {
                "entity_id": entity_id,
                "normalized_value": str(value),
                "normalized_unit": "percent",
                "normalized_currency": None,
                "metric_id": params.get("output_metric_id") or "growth_pct",
                "input_fact_ids": [previous_fact.get("fact_id"), current_fact.get("fact_id")],
            }
        )
    return {"records": records, "count": len(records), "unit": "percent"}


def _ratio_by_entity(inputs: list[Any], params: dict[str, Any]) -> dict[str, Any]:
    if len(inputs) != 2:
        raise OperatorError("ratio_by_entity requires numerator and denominator fact sets")
    numerators = _unique_by_entity(_flatten_facts([inputs[0]]), "numerator")
    denominators = _unique_by_entity(_flatten_facts([inputs[1]]), "denominator")
    records = []
    for entity_id in sorted(set(numerators) & set(denominators)):
        numerator = numerators[entity_id]
        denominator = denominators[entity_id]
        _unit_signature([numerator, denominator])
        base = _fact_value(denominator)
        if base == 0:
            continue
        value = (_fact_value(numerator) / base) * Decimal("100")
        records.append(
            {
                "entity_id": entity_id,
                "normalized_value": str(value),
                "normalized_unit": "percent",
                "normalized_currency": None,
                "metric_id": params.get("output_metric_id") or "ratio_pct",
                "input_fact_ids": [numerator.get("fact_id"), denominator.get("fact_id")],
            }
        )
    return {"records": records, "count": len(records), "unit": "percent"}


def _intersect_on_entity(inputs: list[Any], params: dict[str, Any]) -> dict[str, Any]:
    if len(inputs) != 2:
        raise OperatorError("intersect_on_entity requires a selected set and value set")
    selected_ids = {
        str(row.get("entity_id"))
        for row in _flatten_facts([inputs[0]])
        if row.get("entity_id")
    }
    records = [
        row
        for row in _flatten_facts([inputs[1]])
        if str(row.get("entity_id")) in selected_ids
    ]
    return {"records": records, "count": len(records)}


def _lookup_ranked_entities(inputs: list[Any], params: dict[str, Any]) -> dict[str, Any]:
    if len(inputs) != 2 or not isinstance(inputs[0], dict):
        raise OperatorError("lookup_ranked_entities requires a ranking and secondary facts")
    ranking = inputs[0]
    secondary = _unique_by_entity(_flatten_facts([inputs[1]]), "secondary")
    if not secondary:
        raise OperatorError("lookup_ranked_entities requires secondary facts")
    secondary_unit, secondary_currency = _unit_signature(list(secondary.values()))
    table = []
    for row in ranking.get("table") or []:
        entity_id = str(row.get("entity_id") or "")
        if entity_id not in secondary:
            raise OperatorError(f"Missing secondary fact for ranked entity: {entity_id}")
        fact = secondary[entity_id]
        table.append(
            {
                "rank": row.get("rank"),
                "entity_id": entity_id,
                "primary_value": row.get("value"),
                "secondary_value": str(_fact_value(fact)),
            }
        )
    return {
        "table": table,
        "primary_unit": ranking.get("unit"),
        "primary_currency": ranking.get("currency"),
        "secondary_unit": secondary_unit,
        "secondary_currency": secondary_currency,
    }


def _multi_factor_screen(inputs: list[Any], params: dict[str, Any]) -> dict[str, Any]:
    if len(inputs) != 3:
        raise OperatorError("multi_factor_screen requires growth, margin, and debt records")
    growth = _unique_by_entity(_flatten_facts([inputs[0]]), "growth")
    margin = _unique_by_entity(_flatten_facts([inputs[1]]), "margin")
    debt = _unique_by_entity(_flatten_facts([inputs[2]]), "debt")
    common = sorted(set(growth) & set(margin) & set(debt))
    if not common:
        raise OperatorError("multi_factor_screen has no complete entities")
    industry_average = sum((_fact_value(margin[key]) for key in common), Decimal("0")) / Decimal(len(common))
    growth_min = _decimal(params.get("growth_min_pct", 10))
    debt_max = _decimal(params.get("debt_max_pct", 70))
    table = []
    for entity_id in common:
        growth_value = _fact_value(growth[entity_id])
        margin_value = _fact_value(margin[entity_id])
        debt_value = _fact_value(debt[entity_id])
        if growth_value > growth_min and margin_value > industry_average and debt_value < debt_max:
            table.append(
                {
                    "entity_id": entity_id,
                    "revenue_growth_pct": str(growth_value),
                    "net_margin_pct": str(margin_value),
                    "debt_ratio_pct": str(debt_value),
                }
            )
    table.sort(key=lambda row: (-_decimal(row["net_margin_pct"]), row["entity_id"]))
    return {
        "table": table,
        "industry_average_margin_pct": str(industry_average),
        "growth_threshold_pct": str(growth_min),
        "debt_ratio_max_pct": str(debt_max),
        "unit": "percent",
        "currency": None,
    }


def _unique_by_entity(
    records: list[dict[str, Any]], label: str
) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for record in records:
        entity_id = str(record.get("entity_id") or "")
        if not entity_id:
            raise OperatorError(f"{label} record is missing entity_id")
        if entity_id in output:
            raise OperatorError(f"{label} contains duplicate entity: {entity_id}")
        output[entity_id] = record
    return output


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
    "growth_by_entity": OperatorSpec(
        "growth_by_entity", "paired_entity_fact_sets", "entity_value_set", 2.5, _growth_by_entity
    ),
    "ratio_by_entity": OperatorSpec(
        "ratio_by_entity", "paired_entity_fact_sets", "entity_value_set", 2.0, _ratio_by_entity
    ),
    "intersect_on_entity": OperatorSpec(
        "intersect_on_entity", "entity_value_sets", "entity_value_set", 1.5, _intersect_on_entity
    ),
    "lookup_ranked_entities": OperatorSpec(
        "lookup_ranked_entities", "ranking_and_fact_set", "multi_metric_ranked_table", 2.5, _lookup_ranked_entities
    ),
    "multi_factor_screen": OperatorSpec(
        "multi_factor_screen", "three_entity_value_sets", "screening_table", 3.5, _multi_factor_screen
    ),
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
