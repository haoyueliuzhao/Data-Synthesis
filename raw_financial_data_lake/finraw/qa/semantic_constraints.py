from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Iterable, Mapping

from finraw.qa.comparability import (
    BLOCKED_COMPARABILITY_LEVELS,
    fact_frequency,
    financial_scope_key,
    metric_pair_allowed,
    period_index,
)


SEMANTIC_OPERATOR_REGISTRY_VERSION = "1.2.0"


@dataclass(frozen=True)
class SemanticValidationResult:
    passed: bool
    errors: tuple[str, ...]
    checks: dict[str, dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SemanticConstraintContext:
    spec: Mapping[str, Any]
    binding: Mapping[str, Any]
    fact_map: Mapping[str, dict[str, Any]]
    rows: list[dict[str, Any]]
    metric_ontology: Mapping[str, dict[str, Any]]
    policy: Mapping[str, Any]


@dataclass(frozen=True)
class SemanticCheck:
    name: str
    passed: bool
    observed: Any
    expected: Any


def validate_semantic_constraints(
    pattern_spec: Any,
    binding: Mapping[str, Any],
    facts: Mapping[str, dict[str, Any]] | Iterable[dict[str, Any]],
    metric_ontology: Mapping[str, dict[str, Any]],
    comparability_policy: Mapping[str, Any],
) -> SemanticValidationResult:
    """Execute every declared semantic constraint as a fail-closed gate."""

    spec = _pattern_row(pattern_spec)
    if spec.get("semantic_profile") == "graph_trace":
        comparability_policy = {
            **dict(comparability_policy),
            "require_same_source": False,
            "require_same_time_basis": False,
            "require_same_frequency": False,
            "require_same_seasonal_adjustment": False,
            "require_same_vintage_policy": False,
            "require_same_financial_scope": False,
            "require_same_source_definition": False,
            "require_same_entity_type": False,
        }
    constraints = list(spec.get("semantic_constraints") or [])
    declared = {
        (str(item.get("field") or "").split(".")[-1], str(item.get("operator") or ""))
        for item in constraints
    }
    fact_map = _fact_map(facts)
    bound_ids = _bound_fact_ids(binding)
    rows = [fact_map[fact_id] for fact_id in bound_ids if fact_id in fact_map]
    checks: dict[str, dict[str, Any]] = {}

    def check(name: str, passed: bool, observed: Any, expected: Any) -> None:
        checks[name] = {
            "passed": bool(passed),
            "observed": observed,
            "expected": expected,
        }

    for index, constraint in enumerate(constraints):
        operator = str(constraint.get("operator") or "")
        if operator not in SEMANTIC_OPERATORS:
            check(
                f"unsupported_semantic_operator_{index}_{operator or 'missing'}",
                False,
                operator,
                sorted(SEMANTIC_OPERATORS),
            )

    check(
        "bound_facts_present",
        bool(bound_ids) and len(rows) == len(bound_ids),
        sorted(fact_map),
        bound_ids,
    )
    if not rows:
        return _result(checks)


    # These are baseline admission rules for every executable graph binding.
    not_ready_ids = sorted(
        str(row.get("fact_id"))
        for row in rows
        if not _truthy(row.get("graph_ready"))
    )
    check("graph_ready", not not_ready_ids, not_ready_ids, [])
    forecast_ids = sorted(
        str(row.get("fact_id")) for row in rows if _truthy(row.get("is_forecast"))
    )
    check("forecast_exclusion", not forecast_ids, forecast_ids, [])
    blocked_ids = sorted(
        str(row.get("fact_id"))
        for row in rows
        if _normalise(row.get("comparability_level"))
        in BLOCKED_COMPARABILITY_LEVELS
    )
    check("comparability_level", not blocked_ids, blocked_ids, [])

    if comparability_policy.get("require_same_source", True):
        _same_value_check(
            check,
            "source",
            rows,
            lambda row: row.get("source_id"),
            allow_missing=_allows_missing(constraints, "source", "source_id"),
        )
    if comparability_policy.get("require_same_time_basis", True) or (
        "time_basis", "same"
    ) in declared:
        def time_basis_getter(row: Mapping[str, Any]) -> Any:
            return row.get("time_basis")

        if ("time_basis", "same") in declared:
            _same_value_check(
                check,
                "time_basis",
                rows,
                time_basis_getter,
                allow_missing=_allows_missing(constraints, "time_basis"),
            )
        else:
            _same_value_within_bindings_check(
                check,
                "time_basis",
                binding,
                fact_map,
                time_basis_getter,
                allow_missing=_allows_missing(constraints, "time_basis"),
            )
    if comparability_policy.get("require_same_frequency", True) or (
        "frequency", "same"
    ) in declared:
        _same_value_check(
            check,
            "frequency",
            rows,
            lambda row: row.get("frequency"),
            allow_missing=_allows_missing(constraints, "frequency"),
        )
    if comparability_policy.get("require_same_seasonal_adjustment", True) or (
        "seasonal_adjustment", "same"
    ) in declared:
        _same_value_check(
            check,
            "seasonal_adjustment",
            rows,
            lambda row: _effective_seasonal_adjustment(
                row, metric_ontology
            ),
            allow_missing=_allows_missing(
                constraints, "seasonal_adjustment"
            ),
        )
    if comparability_policy.get("require_same_vintage_policy", True) or (
        "vintage_policy", "same"
    ) in declared:
        _same_value_check(
            check,
            "vintage_policy",
            rows,
            lambda row: row.get("vintage_policy"),
            allow_missing=_allows_missing(constraints, "vintage_policy"),
        )
    if comparability_policy.get("require_same_financial_scope", True) or any(
        field == "financial_scope" for field, _ in declared
    ):
        scope_errors = _financial_scope_errors(rows)
        check("financial_scope", not scope_errors, scope_errors, {})

    if any(field in {"source_definition", "source_definition_id"} for field, _ in declared):
        definition_errors = _source_definition_errors(
            rows,
            require_exact_by_series=bool(
                comparability_policy.get("require_same_source_definition", True)
            ),
        )
        check(
            "source_definition_compatibility",
            not definition_errors,
            definition_errors,
            {},
        )

    if comparability_policy.get("require_same_entity_type", True):
        _same_value_check(
            check,
            "entity_type",
            rows,
            lambda row: row.get("entity_type"),
            allow_missing=_allows_missing(constraints, "entity_type"),
        )

    context = SemanticConstraintContext(
        spec=spec,
        binding=binding,
        fact_map=fact_map,
        rows=rows,
        metric_ontology=metric_ontology,
        policy=comparability_policy,
    )
    for index, constraint in enumerate(constraints):
        evaluator = SEMANTIC_OPERATORS.get(str(constraint.get("operator") or ""))
        if evaluator is None:
            continue
        result = evaluator(context, constraint)
        name = result.name or f"semantic_constraint_{index}"
        if name in checks:
            name = f"{name}_{index}"
        check(name, result.passed, result.observed, result.expected)

    return _result(checks)


def _pattern_row(pattern_spec: Any) -> dict[str, Any]:
    if isinstance(pattern_spec, Mapping):
        return dict(pattern_spec)
    if hasattr(pattern_spec, "as_row"):
        return dict(pattern_spec.as_row())
    raise TypeError("pattern_spec must be a mapping or expose as_row()")


def _fact_map(
    facts: Mapping[str, dict[str, Any]] | Iterable[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    if isinstance(facts, Mapping):
        return {str(key): dict(value) for key, value in facts.items()}
    return {
        str(row["fact_id"]): dict(row)
        for row in facts
        if row.get("fact_id") is not None
    }


def _bound_fact_ids(binding: Mapping[str, Any]) -> list[str]:
    explicit = binding.get("fact_ids")
    if explicit:
        return sorted({str(value) for value in explicit})
    output: set[str] = set()
    for value in dict(binding.get("input_bindings") or {}).values():
        if isinstance(value, list):
            output.update(str(item) for item in value)
        elif value is not None:
            output.add(str(value))
    return sorted(output)


def _metric_role_pair(
    binding: Mapping[str, Any], spec: Mapping[str, Any]
) -> tuple[str, str] | None:
    primary = binding.get("primary_metric_id")
    secondary = binding.get("secondary_metric_id")
    if primary and secondary:
        return str(primary), str(secondary)
    metrics = [str(value) for value in binding.get("metric_ids") or []]
    if len(metrics) >= 2:
        return metrics[0], metrics[1]
    for node in spec.get("node_constraints") or []:
        values = node.get("values")
        if isinstance(values, list) and len(values) >= 2:
            return str(values[0]), str(values[1])
    return None


def _binding_rows(
    binding_name: str,
    binding: Mapping[str, Any],
    fact_map: Mapping[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    value = dict(binding.get("input_bindings") or {}).get(binding_name)
    fact_ids = value if isinstance(value, list) else ([value] if value is not None else [])
    return [fact_map[str(fact_id)] for fact_id in fact_ids if str(fact_id) in fact_map]


def _same_value_check(
    check: Any,
    name: str,
    rows: list[dict[str, Any]],
    getter: Any,
    *,
    allow_missing: bool = False,
) -> None:
    values = sorted({_normalise(getter(row)) for row in rows})
    nonempty = bool(values) and values != [""]
    check(
        f"same_{name}",
        len(values) == 1 and (nonempty or allow_missing),
        values,
        "one compatibility class"
        + ("; missing allowed" if allow_missing else "; non-empty"),
    )


def _same_value_within_bindings_check(
    check: Any,
    name: str,
    binding: Mapping[str, Any],
    fact_map: Mapping[str, dict[str, Any]],
    getter: Any,
    *,
    allow_missing: bool = False,
) -> None:
    observed: dict[str, list[str]] = {}
    passed = True
    input_bindings = dict(binding.get("input_bindings") or {})
    for binding_name in sorted(input_bindings):
        rows = _binding_rows(binding_name, binding, fact_map)
        if not rows:
            continue
        values = sorted({_normalise(getter(row)) for row in rows})
        observed[binding_name] = values
        nonempty = bool(values) and values != [""]
        passed = passed and len(values) == 1 and (nonempty or allow_missing)
    check(
        f"same_{name}",
        bool(observed) and passed,
        observed,
        "one compatibility class per input binding"
        + ("; missing allowed" if allow_missing else "; non-empty"),
    )


def _allows_missing(
    constraints: Iterable[Mapping[str, Any]],
    *field_names: str,
) -> bool:
    expected = {str(value) for value in field_names}
    return any(
        str(constraint.get("field") or "").split(".")[-1] in expected
        and str(constraint.get("operator") or "") == "same"
        and _truthy(constraint.get("allow_missing"))
        for constraint in constraints
    )


def _financial_scope_errors(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_entity: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for row in rows:
        by_entity[str(row.get("entity_id") or "")].add(financial_scope_key(row))
    errors: dict[str, Any] = {
        entity_id: [list(value) for value in sorted(scopes)]
        for entity_id, scopes in by_entity.items()
        if len(scopes) > 1
    }
    scope_types = {
        str(row.get("financial_scope_type") or "consolidated_entity")
        for row in rows
    }
    if len(scope_types) > 1:
        errors["mixed_scope_type_across_entities"] = sorted(scope_types)
    invalid_consolidated = sorted(
        str(row.get("fact_id"))
        for row in rows
        if str(row.get("financial_scope_type") or "consolidated_entity")
        == "consolidated_entity"
        and row.get("entity_scope_id")
        and str(row.get("entity_scope_id")) != str(row.get("entity_id"))
    )
    if invalid_consolidated:
        errors["misaligned_consolidated_scope"] = invalid_consolidated
    if len(by_entity) > 1 and scope_types != {"consolidated_entity"}:
        scope_ids = {
            str(row.get("entity_scope_id") or "") for row in rows
        }
        if len(scope_ids) > 1:
            errors["noncanonical_cross_entity_scope"] = sorted(scope_ids)
    return errors


def _source_definition_errors(
    rows: list[dict[str, Any]], *, require_exact_by_series: bool
) -> dict[str, Any]:
    errors: dict[str, Any] = {}
    missing = sorted(
        str(row.get("fact_id"))
        for row in rows
        if not _normalise(row.get("source_definition_id"))
    )
    if missing:
        errors["missing_source_definition"] = missing
    by_series: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in rows:
        by_series[(str(row.get("entity_id")), str(row.get("metric_id")))].add(
            _normalise(row.get("source_definition_id"))
        )
    mixed_series = {
        "|".join(key): sorted(values)
        for key, values in by_series.items()
        if require_exact_by_series and len(values) > 1
    }
    if mixed_series:
        errors["mixed_definition_within_series"] = mixed_series

    classes = {
        (
            _normalise(row.get("source_id")),
            _normalise(fact_frequency(row)),
            _normalise(row.get("time_basis")),
            _normalise(row.get("seasonal_adjustment")),
            _normalise(row.get("vintage_policy")),
            _normalise(row.get("comparability_level") or "comparable"),
        )
        for row in rows
    }
    if len(classes) > 1:
        errors["mixed_compatibility_class"] = [list(value) for value in sorted(classes)]
    return errors


SemanticEvaluator = Callable[
    [SemanticConstraintContext, Mapping[str, Any]], SemanticCheck
]


def _evaluate_eq(
    context: SemanticConstraintContext, constraint: Mapping[str, Any]
) -> SemanticCheck:
    field = str(constraint.get("field") or "")
    suffix = field.split(".")[-1]
    expected = constraint.get("value")
    getters = {
        "graph_ready": lambda row: _truthy(row.get("graph_ready")),
        "is_forecast": lambda row: _truthy(row.get("is_forecast")),
        "entity_type": lambda row: _normalise(row.get("entity_type")),
        "frequency": lambda row: _normalise(fact_frequency(row)),
        "fiscal_quarter": lambda row: _normalise(row.get("fiscal_quarter")),
    }
    if suffix in getters:
        observed = sorted({getters[suffix](row) for row in context.rows}, key=str)
        expected_value = (
            _truthy(expected)
            if suffix in {"graph_ready", "is_forecast"}
            else _normalise(expected)
        )
        return SemanticCheck(
            f"{suffix}_equals",
            observed == [expected_value],
            observed,
            [expected_value],
        )
    if field == "secondary_period_coverage":
        return _coverage_check(
            context,
            field,
            "primary_series",
            "secondary_series",
            expected,
            by_period=True,
        )
    if field == "secondary_entity_coverage":
        return _coverage_check(
            context,
            field,
            "revenue",
            "total_assets",
            expected,
            by_period=False,
        )
    if field == "scope_input_coverage":
        expected_ids = {str(value) for value in context.binding.get("entity_ids") or []}
        entity_sets = _input_entity_sets(context)
        binding_rows = {
            str(name): _binding_rows(str(name), context.binding, context.fact_map)
            for name in dict(context.binding.get("input_bindings") or {})
        }
        unique = all(
            len(rows)
            == len({str(row.get("entity_id")) for row in rows if row.get("entity_id")})
            for rows in binding_rows.values()
        )
        exact = bool(expected_ids) and bool(entity_sets) and all(
            values == expected_ids for values in entity_sets.values()
        ) and unique
        observed_ratio = Decimal("1") if exact else _minimum_set_coverage(
            entity_sets.values(), expected_ids
        )
        expected_ratio = _decimal(expected)
        return SemanticCheck(
            "scope_input_coverage_equals",
            expected_ratio is not None and observed_ratio == expected_ratio and exact,
            {
                "coverage": str(observed_ratio),
                "entity_sets": {
                    name: sorted(values) for name, values in entity_sets.items()
                },
                "unique_entity_fact_per_binding": unique,
            },
            {"coverage": str(expected_ratio), "entity_ids": sorted(expected_ids)},
        )
    return _unsupported_field("eq", field)


def _evaluate_ne(
    context: SemanticConstraintContext, constraint: Mapping[str, Any]
) -> SemanticCheck:
    field = str(constraint.get("field") or "")
    other = str(constraint.get("value_from") or "")
    role_aliases = {"left_entity": "left", "right_entity": "right"}
    if field not in role_aliases or other not in role_aliases:
        return _unsupported_field("ne", field)
    left = {
        str(row.get("entity_id"))
        for row in _binding_rows(role_aliases[field], context.binding, context.fact_map)
        if row.get("entity_id")
    }
    right = {
        str(row.get("entity_id"))
        for row in _binding_rows(role_aliases[other], context.binding, context.fact_map)
        if row.get("entity_id")
    }
    return SemanticCheck(
        f"{_safe_name(field)}_not_equal_{_safe_name(other)}",
        bool(left) and bool(right) and left.isdisjoint(right),
        {field: sorted(left), other: sorted(right)},
        "disjoint non-empty entity sets",
    )


def _evaluate_gte(
    context: SemanticConstraintContext, constraint: Mapping[str, Any]
) -> SemanticCheck:
    field = str(constraint.get("field") or "")
    if not field.endswith(".count"):
        return _unsupported_field("gte", field)
    variable = field.rsplit(".", 1)[0]
    aliases = {
        "facts": "series",
        "primary_facts": "primary_series",
        "secondary_facts": "secondary_series",
    }
    binding_name = aliases.get(variable, variable)
    rows = _binding_rows(binding_name, context.binding, context.fact_map)
    count = len({str(row.get("fact_id")) for row in rows})
    expected = _decimal(constraint.get("value"))
    return SemanticCheck(
        f"{_safe_name(variable)}_count_gte",
        expected is not None and Decimal(count) >= expected,
        count,
        str(expected),
    )


def _evaluate_same(
    context: SemanticConstraintContext, constraint: Mapping[str, Any]
) -> SemanticCheck:
    field = str(constraint.get("field") or "")
    row_getters = {
        "source": lambda row: row.get("source_id"),
        "source_id": lambda row: row.get("source_id"),
        "entity_type": lambda row: row.get("entity_type"),
        "time_basis": lambda row: row.get("time_basis"),
        "frequency": fact_frequency,
        "seasonal_adjustment": lambda row: _effective_seasonal_adjustment(
            row, context.metric_ontology
        ),
        "vintage_policy": lambda row: row.get("vintage_policy"),
        "unit": lambda row: row.get("normalized_unit"),
        "currency": lambda row: row.get("normalized_currency"),
        "source_definition": lambda row: row.get("source_definition_id"),
        "period": _period_alignment_signature,
        "entity.industry": lambda row: row.get("industry"),
    }
    if field in row_getters:
        values = sorted({_normalise(row_getters[field](row)) for row in context.rows})
        nonempty = bool(values) and values != [""]
        allow_missing = _truthy(constraint.get("allow_missing"))
        return SemanticCheck(
            f"same_{_safe_name(field)}",
            len(values) == 1 and (nonempty or allow_missing),
            values,
            "one value; missing allowed"
            if allow_missing
            else "one non-empty value",
        )
    if field == "scope":
        values = sorted({_normalise(_entity_scope_label(row)) for row in context.rows})
        expected = _normalise(context.binding.get("scope_definition"))
        return SemanticCheck(
            "same_scope",
            bool(values)
            and values != [""]
            and len(values) == 1
            and (not expected or values == [expected]),
            values,
            [expected] if expected else "one canonical scope",
        )
    if field == "financial_scope":
        errors = _financial_scope_errors(context.rows)
        return SemanticCheck("financial_scope", not errors, errors, {})
    if field == "statement_type":
        return _ontology_semantic_check(context, "statement_type")
    if field in {"metric_period_type", "period_type"}:
        return _ontology_semantic_check(context, "period_type")
    return _unsupported_field("same", field)


def _evaluate_compatible(
    context: SemanticConstraintContext, constraint: Mapping[str, Any]
) -> SemanticCheck:
    field = str(constraint.get("field") or "")
    if field in {"unit", "currency"}:
        key = "normalized_unit" if field == "unit" else "normalized_currency"
        values = sorted({_normalise(row.get(key)) for row in context.rows})
        return SemanticCheck(
            f"compatible_{field}",
            len(values) == 1 and values != [""],
            values,
            "one non-empty compatibility class",
        )
    if field in {"source_definition", "source_definition_id"}:
        errors = _source_definition_errors(context.rows, require_exact_by_series=True)
        return SemanticCheck(
            "source_definition_compatibility", not errors, errors, {}
        )
    return _unsupported_field("compatible", field)


def _evaluate_compatible_by_series(
    context: SemanticConstraintContext, constraint: Mapping[str, Any]
) -> SemanticCheck:
    field = str(constraint.get("field") or "")
    if field not in {"source_definition", "source_definition_id"}:
        return _unsupported_field("compatible_by_series", field)
    errors = _source_definition_errors(context.rows, require_exact_by_series=True)
    return SemanticCheck(
        "source_definition_compatible_by_series", not errors, errors, {}
    )


def _evaluate_contiguous(
    context: SemanticConstraintContext, constraint: Mapping[str, Any]
) -> SemanticCheck:
    field = str(constraint.get("field") or "")
    if field != "periods":
        return _unsupported_field("contiguous", field)
    input_bindings = dict(context.binding.get("input_bindings") or {})
    series_names = [
        name
        for name, value in input_bindings.items()
        if isinstance(value, list) and ("series" in name or name == "series")
    ]
    if not series_names and len(input_bindings) == 1:
        series_names = list(input_bindings)
    observed: dict[str, Any] = {}
    passed = bool(series_names)
    for name in series_names:
        rows = _binding_rows(name, context.binding, context.fact_map)
        frequencies = {_normalise(fact_frequency(row)) for row in rows}
        frequency = next(iter(frequencies), "")
        indices = [period_index(row, frequency) for row in rows]
        ordered = sorted(value for value in indices if value is not None)
        valid = (
            bool(rows)
            and len(frequencies) == 1
            and len(ordered) == len(rows)
            and len(set(ordered)) == len(ordered)
            and all(right - left == 1 for left, right in zip(ordered, ordered[1:]))
        )
        observed[name] = {"indices": ordered, "frequency": frequency, "passed": valid}
        passed = passed and valid
    return SemanticCheck("periods_contiguous", passed, observed, "step size 1")


def _evaluate_between_days(
    context: SemanticConstraintContext, constraint: Mapping[str, Any]
) -> SemanticCheck:
    field = str(constraint.get("field") or "")
    if field != "annual_flow_duration":
        return _unsupported_field("between_days", field)
    bounds = constraint.get("value")
    if not isinstance(bounds, (list, tuple)) or len(bounds) != 2:
        return _unsupported_field("between_days", field)
    lower = _decimal(bounds[0])
    upper = _decimal(bounds[1])
    invalid: dict[str, Any] = {}
    if lower is None or upper is None or lower > upper:
        invalid["constraint_bounds"] = bounds
    else:
        for row in context.rows:
            if fact_frequency(row) != "annual":
                continue
            if str(row.get("metric_period_type") or "") == "point_in_time":
                continue
            days = _duration_days(row)
            if days is None or not lower <= Decimal(days) <= upper:
                invalid[str(row.get("fact_id"))] = days
    return SemanticCheck(
        "annual_flow_duration",
        not invalid,
        invalid,
        {"minimum_days": str(lower), "maximum_days": str(upper)},
    )


def _evaluate_consolidated_entity(
    context: SemanticConstraintContext, constraint: Mapping[str, Any]
) -> SemanticCheck:
    field = str(constraint.get("field") or "")
    if field != "financial_scope":
        return _unsupported_field("consolidated_entity", field)
    invalid = sorted(
        str(row.get("fact_id"))
        for row in context.rows
        if financial_scope_key(row)
        != (str(row.get("entity_id") or ""), "consolidated_entity")
    )
    return SemanticCheck("consolidated_entity_scope", not invalid, invalid, [])


def _evaluate_complete_across_bindings(
    context: SemanticConstraintContext, constraint: Mapping[str, Any]
) -> SemanticCheck:
    field = str(constraint.get("field") or "")
    if field != "scope_entities":
        return _unsupported_field("complete_across_bindings", field)
    names = [str(value) for value in constraint.get("bindings") or []]
    entity_sets = {
        name: {
            str(row.get("entity_id"))
            for row in _binding_rows(name, context.binding, context.fact_map)
            if row.get("entity_id")
        }
        for name in names
    }
    expected = {str(value) for value in context.binding.get("entity_ids") or []}
    unique = all(
        len(_binding_rows(name, context.binding, context.fact_map))
        == len(values)
        for name, values in entity_sets.items()
    )
    complete = bool(entity_sets) and bool(expected) and unique and all(
        values == expected for values in entity_sets.values()
    )
    return SemanticCheck(
        "scope_entity_coverage",
        complete,
        {
            "entity_sets": {
                name: sorted(values) for name, values in entity_sets.items()
            },
            "unique_entity_fact_per_binding": unique,
        },
        sorted(expected),
    )


def _evaluate_binding_property(
    context: SemanticConstraintContext,
    constraint: Mapping[str, Any],
    operator: str,
) -> SemanticCheck:
    field = str(constraint.get("field") or "")
    if "." not in field:
        return _unsupported_field(operator, field)
    binding_name, fact_field = field.split(".", 1)
    getters = {
        "entity_id": lambda row: row.get("entity_id"),
        "unit": lambda row: row.get("normalized_unit"),
        "currency": lambda row: row.get("normalized_currency"),
        "source_definition_id": lambda row: row.get("source_definition_id"),
    }
    getter = getters.get(fact_field)
    if getter is None:
        return _unsupported_field(operator, field)
    rows = _binding_rows(binding_name, context.binding, context.fact_map)
    values = [_normalise(getter(row)) for row in rows]
    if operator == "unique":
        passed = bool(rows) and len(values) == len(set(values)) and "" not in values
        expected: Any = "unique non-empty values"
    else:
        passed = bool(rows) and len(set(values)) == 1 and values[0] != ""
        expected = "one non-empty value"
    return SemanticCheck(
        f"{binding_name}_{fact_field}_{'unique' if operator == 'unique' else 'consistent'}",
        passed,
        values,
        expected,
    )


def _evaluate_unique(
    context: SemanticConstraintContext, constraint: Mapping[str, Any]
) -> SemanticCheck:
    return _evaluate_binding_property(context, constraint, "unique")


def _evaluate_same_within_binding(
    context: SemanticConstraintContext, constraint: Mapping[str, Any]
) -> SemanticCheck:
    return _evaluate_binding_property(context, constraint, "same_within_binding")


def _evaluate_registered_comparable_pair(
    context: SemanticConstraintContext, constraint: Mapping[str, Any]
) -> SemanticCheck:
    if str(constraint.get("field") or "") != "metric_pair":
        return _unsupported_field(str(constraint.get("operator")), str(constraint.get("field")))
    pair = _metric_role_pair(context.binding, context.spec)
    allowed = bool(pair) and metric_pair_allowed(pair[0], pair[1], dict(context.policy))
    return SemanticCheck(
        "registered_comparable_metric_pair",
        allowed,
        list(pair) if pair else [],
        [list(value) for value in context.policy.get("allowed_metric_pairs", ())],
    )


def _evaluate_registered_followup_pair(
    context: SemanticConstraintContext, constraint: Mapping[str, Any]
) -> SemanticCheck:
    if str(constraint.get("field") or "") != "metric_pair":
        return _unsupported_field(str(constraint.get("operator")), str(constraint.get("field")))
    pair = _metric_role_pair(context.binding, context.spec)
    allowed_pairs = {
        (str(left), str(right))
        for left, right in context.policy.get("followup_metric_pairs", ())
    }
    return SemanticCheck(
        "registered_followup_metric_pair",
        bool(pair) and pair in allowed_pairs,
        list(pair) if pair else [],
        [list(value) for value in sorted(allowed_pairs)],
    )


def _evaluate_gt(
    context: SemanticConstraintContext, constraint: Mapping[str, Any]
) -> SemanticCheck:
    field = str(constraint.get("field") or "")
    if field != "revenue_growth_pct":
        return _unsupported_field("gt", field)
    values = _growth_values(context)
    configured = _operation_parameter(
        context, (("filter", "value"), ("multi_factor_screen", "growth_min_pct"))
    )
    fallback = _decimal(context.policy.get("growth_threshold_pct"))
    expected = configured if configured is not None else fallback
    allowed = {
        value
        for value in (
            _decimal(item)
            for item in context.policy.get(
                "growth_thresholds_pct", (context.policy.get("growth_threshold_pct"),)
            )
        )
        if value is not None
    }
    qualifying = sorted(key for key, value in values.items() if expected is not None and value > expected)
    passed = (
        bool(values)
        and bool(qualifying)
        and expected is not None
        and configured == expected
        and expected in allowed
    )
    return SemanticCheck(
        "revenue_growth_pct_gt_policy",
        passed,
        {"values": _decimal_map(values), "configured_threshold": str(configured), "qualifying": qualifying},
        {
            "threshold": str(expected),
            "allowed_thresholds": [str(value) for value in sorted(allowed)],
            "comparison": "gt",
        },
    )


def _evaluate_lt(
    context: SemanticConstraintContext, constraint: Mapping[str, Any]
) -> SemanticCheck:
    field = str(constraint.get("field") or "")
    if field != "debt_ratio_pct":
        return _unsupported_field("lt", field)
    values = _ratio_values(context, "total_liabilities", "total_assets")
    configured = _operation_parameter(context, (("multi_factor_screen", "debt_max_pct"),))
    fallback = _decimal(context.policy.get("debt_ratio_max_pct"))
    expected = configured if configured is not None else fallback
    allowed = {
        value
        for value in (
            _decimal(item)
            for item in context.policy.get(
                "debt_ratio_thresholds_pct",
                (context.policy.get("debt_ratio_max_pct"),),
            )
        )
        if value is not None
    }
    qualifying = sorted(key for key, value in values.items() if expected is not None and value < expected)
    passed = (
        bool(values)
        and bool(qualifying)
        and expected is not None
        and configured == expected
        and expected in allowed
    )
    return SemanticCheck(
        "debt_ratio_pct_lt_policy",
        passed,
        {"values": _decimal_map(values), "configured_threshold": str(configured), "qualifying": qualifying},
        {
            "threshold": str(expected),
            "allowed_thresholds": [str(value) for value in sorted(allowed)],
            "comparison": "lt",
        },
    )


def _evaluate_gt_industry_average(
    context: SemanticConstraintContext, constraint: Mapping[str, Any]
) -> SemanticCheck:
    field = str(constraint.get("field") or "")
    if field != "net_margin":
        return _unsupported_field("gt_industry_average", field)
    values = _ratio_values(context, "net_income", "current_revenue")
    average = sum(values.values(), Decimal("0")) / Decimal(len(values)) if values else None
    qualifying = sorted(
        key for key, value in values.items() if average is not None and value > average
    )
    return SemanticCheck(
        "net_margin_gt_industry_average",
        bool(values) and bool(qualifying),
        {"values": _decimal_map(values), "average": str(average), "qualifying": qualifying},
        "at least one entity above the recomputed scope average",
    )


SEMANTIC_OPERATORS: dict[str, SemanticEvaluator] = {
    "eq": _evaluate_eq,
    "ne": _evaluate_ne,
    "gte": _evaluate_gte,
    "gt": _evaluate_gt,
    "lt": _evaluate_lt,
    "same": _evaluate_same,
    "compatible": _evaluate_compatible,
    "compatible_by_series": _evaluate_compatible_by_series,
    "contiguous": _evaluate_contiguous,
    "between_days": _evaluate_between_days,
    "consolidated_entity": _evaluate_consolidated_entity,
    "complete_across_bindings": _evaluate_complete_across_bindings,
    "same_within_binding": _evaluate_same_within_binding,
    "unique": _evaluate_unique,
    "registered_comparable_pair": _evaluate_registered_comparable_pair,
    "registered_comparable_metric_pair": _evaluate_registered_comparable_pair,
    "registered_followup_pair": _evaluate_registered_followup_pair,
    "registered_followup_metric_pair": _evaluate_registered_followup_pair,
    "gt_industry_average": _evaluate_gt_industry_average,
}


def semantic_operator_manifest() -> dict[str, Any]:
    """Return the frozen public contract for semantic constraint operators."""
    return {
        "registry_version": SEMANTIC_OPERATOR_REGISTRY_VERSION,
        "operators": {
            name: {"evaluator": evaluator.__name__}
            for name, evaluator in sorted(SEMANTIC_OPERATORS.items())
        },
    }


def _coverage_check(
    context: SemanticConstraintContext,
    field: str,
    primary_binding: str,
    secondary_binding: str,
    expected_value: Any,
    *,
    by_period: bool,
) -> SemanticCheck:
    primary_rows = _binding_rows(primary_binding, context.binding, context.fact_map)
    secondary_rows = _binding_rows(secondary_binding, context.binding, context.fact_map)
    if by_period:
        primary = {_period_alignment_signature(row) for row in primary_rows}
        secondary = {_period_alignment_signature(row) for row in secondary_rows}
    else:
        primary = {str(row.get("entity_id")) for row in primary_rows if row.get("entity_id")}
        secondary = {str(row.get("entity_id")) for row in secondary_rows if row.get("entity_id")}
    unique = len(primary_rows) == len(primary) and len(secondary_rows) == len(secondary)
    ratio = Decimal(len(primary & secondary)) / Decimal(len(primary)) if primary else Decimal("0")
    expected = _decimal(expected_value)
    return SemanticCheck(
        f"{field}_equals",
        expected is not None
        and ratio == expected
        and primary == secondary
        and unique,
        {
            "coverage": str(ratio),
            "primary": sorted(primary),
            "secondary": sorted(secondary),
            "unique_binding_keys": unique,
        },
        {"coverage": str(expected), "exact_set_match": True},
    )


def _input_entity_sets(context: SemanticConstraintContext) -> dict[str, set[str]]:
    return {
        str(name): {
            str(row.get("entity_id"))
            for row in _binding_rows(str(name), context.binding, context.fact_map)
            if row.get("entity_id")
        }
        for name in dict(context.binding.get("input_bindings") or {})
    }


def _minimum_set_coverage(values: Iterable[set[str]], expected: set[str]) -> Decimal:
    if not expected:
        return Decimal("0")
    ratios = [Decimal(len(value & expected)) / Decimal(len(expected)) for value in values]
    return min(ratios, default=Decimal("0"))


def _ontology_semantic_check(
    context: SemanticConstraintContext, field: str
) -> SemanticCheck:
    missing = sorted(
        {str(row.get("metric_id")) for row in context.rows if str(row.get("metric_id")) not in context.metric_ontology}
    )
    values = sorted(
        {
            _normalise(
                context.metric_ontology.get(str(row.get("metric_id")), {}).get(field)
                or (row.get("metric_period_type") if field == "period_type" else row.get(field))
            )
            for row in context.rows
        }
    )
    return SemanticCheck(
        f"same_{field}",
        not missing and len(values) == 1 and values != [""],
        {"values": values, "missing_metrics": missing},
        {"values": "one ontology class", "missing_metrics": []},
    )


def _period_signature(row: Mapping[str, Any]) -> str:
    return "|".join(
        str(value or "")
        for value in (
            row.get("fiscal_year"),
            row.get("fiscal_quarter"),
            row.get("calendar_year"),
            row.get("period_end"),
            row.get("as_of_date"),
        )
    )


def _period_alignment_signature(row: Mapping[str, Any]) -> str:
    frequency = fact_frequency(dict(row))
    index = period_index(dict(row), frequency)
    if index is not None:
        return f"{frequency}:{index}"
    return _period_signature(row)


def _entity_scope_label(row: Mapping[str, Any]) -> Any:
    if _normalise(row.get("entity_type")) == "company":
        return row.get("industry")
    return row.get("country") or row.get("market") or row.get("entity_type")


def _effective_seasonal_adjustment(
    row: Mapping[str, Any],
    metric_ontology: Mapping[str, dict[str, Any]],
) -> Any:
    explicit = row.get("seasonal_adjustment")
    if _normalise(explicit):
        return explicit
    metric = metric_ontology.get(str(row.get("metric_id")), {})
    if (
        fact_frequency(dict(row)) == "annual"
        or _normalise(metric.get("metric_category")) == "financial_statement"
        or _normalise(metric.get("statement_type"))
        in {"income_statement", "balance_sheet", "cash_flow"}
    ):
        return "not_applicable"
    return None


def _growth_values(context: SemanticConstraintContext) -> dict[str, Decimal]:
    current = _rows_by_entity(_binding_rows("current_revenue", context.binding, context.fact_map))
    previous = _rows_by_entity(_binding_rows("previous_revenue", context.binding, context.fact_map))
    output: dict[str, Decimal] = {}
    for entity_id in sorted(set(current) & set(previous)):
        current_value = _fact_decimal(current[entity_id])
        previous_value = _fact_decimal(previous[entity_id])
        if current_value is None or previous_value in {None, Decimal("0")}:
            continue
        output[entity_id] = ((current_value - previous_value) / abs(previous_value)) * Decimal("100")
    return output


def _ratio_values(
    context: SemanticConstraintContext, numerator_binding: str, denominator_binding: str
) -> dict[str, Decimal]:
    numerators = _rows_by_entity(_binding_rows(numerator_binding, context.binding, context.fact_map))
    denominators = _rows_by_entity(_binding_rows(denominator_binding, context.binding, context.fact_map))
    output: dict[str, Decimal] = {}
    for entity_id in sorted(set(numerators) & set(denominators)):
        numerator = _fact_decimal(numerators[entity_id])
        denominator = _fact_decimal(denominators[entity_id])
        if numerator is None or denominator in {None, Decimal("0")}:
            continue
        output[entity_id] = (numerator / denominator) * Decimal("100")
    return output


def _rows_by_entity(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for row in rows:
        entity_id = str(row.get("entity_id") or "")
        if entity_id and entity_id not in output:
            output[entity_id] = row
    return output


def _operation_parameter(
    context: SemanticConstraintContext, candidates: tuple[tuple[str, str], ...]
) -> Decimal | None:
    overrides = dict(context.binding.get("operator_step_params") or {})
    for step in context.spec.get("operator_template", {}).get("operators") or []:
        operator = str(step.get("operator") or "")
        step_id = str(step.get("step_id") or "")
        params = {**dict(step.get("params") or {}), **dict(overrides.get(step_id) or {})}
        for expected_operator, parameter in candidates:
            if operator == expected_operator and parameter in params:
                return _decimal(params.get(parameter))
    return None


def _fact_decimal(row: Mapping[str, Any]) -> Decimal | None:
    return _decimal(row.get("normalized_value"))


def _duration_days(row: Mapping[str, Any]) -> int | None:
    try:
        start = date.fromisoformat(str(row.get("period_start"))[:10])
        end = date.fromisoformat(str(row.get("period_end"))[:10])
    except (TypeError, ValueError):
        return None
    return (end - start).days


def _decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _decimal_map(values: Mapping[str, Decimal]) -> dict[str, str]:
    return {key: str(value) for key, value in sorted(values.items())}


def _unsupported_field(operator: str, field: str) -> SemanticCheck:
    return SemanticCheck(
        f"unsupported_semantic_field_{_safe_name(operator)}_{_safe_name(field)}",
        False,
        {"operator": operator, "field": field},
        "registered operator/field combination",
    )


def _safe_name(value: str) -> str:
    return "".join(character if character.isalnum() else "_" for character in value).strip("_")


def _result(checks: dict[str, dict[str, Any]]) -> SemanticValidationResult:
    errors = tuple(sorted(name for name, value in checks.items() if not value["passed"]))
    return SemanticValidationResult(not errors, errors, checks)


def _normalise(value: Any) -> str:
    return str(value or "").strip().lower()


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)
