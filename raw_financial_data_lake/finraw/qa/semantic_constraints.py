from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping

from finraw.qa.comparability import (
    BLOCKED_COMPARABILITY_LEVELS,
    annual_duration_valid,
    fact_frequency,
    financial_scope_key,
    metric_pair_allowed,
)


@dataclass(frozen=True)
class SemanticValidationResult:
    passed: bool
    errors: tuple[str, ...]
    checks: dict[str, dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_semantic_constraints(
    pattern_spec: Any,
    binding: Mapping[str, Any],
    facts: Mapping[str, dict[str, Any]] | Iterable[dict[str, Any]],
    metric_ontology: Mapping[str, dict[str, Any]],
    comparability_policy: Mapping[str, Any],
) -> SemanticValidationResult:
    """Execute graph-pattern semantic constraints against bound facts.

    The same validator is used by motif mining, candidate construction, and
    final QA verification. Unknown descriptive constraints are left to their
    specialised matcher; every comparability constraint handled here is a
    fail-closed quality gate.
    """

    spec = _pattern_row(pattern_spec)
    constraints = list(spec.get("semantic_constraints") or [])
    declared = {
        (str(item.get("field") or "").split(".")[-1], str(item.get("operator") or ""))
        for item in constraints
    }
    operators = {operator for _, operator in declared}
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
        _same_value_check(check, "source", rows, lambda row: row.get("source_id"))
    if comparability_policy.get("require_same_time_basis", True) or (
        "time_basis", "same"
    ) in declared:
        _same_value_check(check, "time_basis", rows, lambda row: row.get("time_basis"))
    if comparability_policy.get("require_same_frequency", True) or (
        "frequency", "same"
    ) in declared:
        _same_value_check(check, "frequency", rows, fact_frequency)
    if comparability_policy.get("require_same_seasonal_adjustment", True) or (
        "seasonal_adjustment", "same"
    ) in declared:
        _same_value_check(
            check,
            "seasonal_adjustment",
            rows,
            lambda row: row.get("seasonal_adjustment"),
        )
    if comparability_policy.get("require_same_vintage_policy", True) or (
        "vintage_policy", "same"
    ) in declared:
        _same_value_check(
            check,
            "vintage_policy",
            rows,
            lambda row: row.get("vintage_policy"),
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

    _validate_exact_constraints(check, constraints, binding, rows)
    _validate_binding_constraints(check, constraints, binding, fact_map)

    if ("metric_pair", "registered_comparable_pair") in declared or (
        "metric_pair",
        "registered_comparable_metric_pair",
    ) in declared:
        pair = _metric_role_pair(binding, spec)
        allowed = bool(pair) and metric_pair_allowed(pair[0], pair[1], dict(comparability_policy))
        check(
            "registered_comparable_metric_pair",
            allowed,
            list(pair) if pair else [],
            [list(value) for value in comparability_policy.get("allowed_metric_pairs", ())],
        )

    if "registered_followup_pair" in operators or "registered_followup_metric_pair" in operators:
        pair = _metric_role_pair(binding, spec)
        allowed_pairs = {
            (str(left), str(right))
            for left, right in comparability_policy.get("followup_metric_pairs", ())
        }
        check(
            "registered_followup_metric_pair",
            bool(pair) and pair in allowed_pairs,
            list(pair) if pair else [],
            [list(value) for value in sorted(allowed_pairs)],
        )

    if ("statement_type", "same") in declared:
        _ontology_same_check(check, "statement_type", rows, metric_ontology)
    if ("metric_period_type", "same") in declared or (
        "period_type",
        "same",
    ) in declared:
        _ontology_same_check(check, "period_type", rows, metric_ontology)
    if comparability_policy.get("require_same_entity_type", True) or (
        "entity_type", "same"
    ) in declared:
        _same_value_check(
            check, "entity_type", rows, lambda row: row.get("entity_type")
        )
    if ("unit", "same") in declared or ("unit", "compatible") in declared:
        _same_value_check(
            check, "unit", rows, lambda row: row.get("normalized_unit")
        )
    if ("currency", "same") in declared or (
        "currency",
        "compatible",
    ) in declared:
        _same_value_check(
            check,
            "currency",
            rows,
            lambda row: row.get("normalized_currency"),
        )

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


def _validate_exact_constraints(
    check: Any,
    constraints: list[dict[str, Any]],
    binding: Mapping[str, Any],
    rows: list[dict[str, Any]],
) -> None:
    field_getters = {
        "entity_type": lambda row: row.get("entity_type"),
        "frequency": fact_frequency,
        "fiscal_quarter": lambda row: row.get("fiscal_quarter"),
    }
    for constraint in constraints:
        field = str(constraint.get("field") or "")
        operator = str(constraint.get("operator") or "")
        if operator == "eq" and field in field_getters:
            observed = sorted({_normalise(field_getters[field](row)) for row in rows})
            expected = _normalise(constraint.get("value"))
            check(
                f"{field}_equals",
                observed == [expected],
                observed,
                [expected],
            )
        elif field == "financial_scope" and operator == "consolidated_entity":
            invalid = sorted(
                str(row.get("fact_id"))
                for row in rows
                if financial_scope_key(row)
                != (str(row.get("entity_id") or ""), "consolidated_entity")
            )
            check(
                "consolidated_entity_scope",
                not invalid,
                invalid,
                [],
            )
        elif field == "annual_flow_duration" and operator == "between_days":
            invalid = sorted(
                str(row.get("fact_id"))
                for row in rows
                if not annual_duration_valid(row)
            )
            check("annual_flow_duration", not invalid, invalid, [])
        elif field == "scope_entities" and operator == "complete_across_bindings":
            names = [str(value) for value in constraint.get("bindings") or []]
            entity_sets = {
                name: sorted(
                    {
                        str(row.get("entity_id"))
                        for row in _binding_rows(name, binding, _fact_map(rows))
                    }
                )
                for name in names
            }
            expected_entities = sorted(
                str(value) for value in binding.get("entity_ids") or []
            )
            sets = [set(values) for values in entity_sets.values()]
            complete = bool(sets) and all(value == sets[0] for value in sets[1:])
            if expected_entities:
                complete = complete and sets[0] == set(expected_entities)
            check(
                "scope_entity_coverage",
                complete,
                entity_sets,
                expected_entities or "identical entity sets",
            )


def _validate_binding_constraints(
    check: Any,
    constraints: list[dict[str, Any]],
    binding: Mapping[str, Any],
    fact_map: Mapping[str, dict[str, Any]],
) -> None:
    field_getters = {
        "entity_id": lambda row: row.get("entity_id"),
        "unit": lambda row: row.get("normalized_unit"),
        "currency": lambda row: row.get("normalized_currency"),
        "source_definition_id": lambda row: row.get("source_definition_id"),
    }
    for constraint in constraints:
        field = str(constraint.get("field") or "")
        operator = str(constraint.get("operator") or "")
        if "." not in field or operator not in {"same_within_binding", "unique"}:
            continue
        binding_name, fact_field = field.split(".", 1)
        getter = field_getters.get(fact_field)
        if getter is None:
            continue
        bound_rows = _binding_rows(binding_name, binding, fact_map)
        values = [_normalise(getter(row)) for row in bound_rows]
        if operator == "same_within_binding":
            check(
                f"{binding_name}_{fact_field}_consistent",
                bool(bound_rows) and len(set(values)) == 1,
                sorted(set(values)),
                "one value",
            )
        else:
            check(
                f"{binding_name}_{fact_field}_unique",
                bool(bound_rows) and len(values) == len(set(values)),
                values,
                "no duplicates",
            )


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
) -> None:
    values = sorted({_normalise(getter(row)) for row in rows})
    check(f"same_{name}", len(values) <= 1, values, "one compatibility class")


def _ontology_same_check(
    check: Any,
    field: str,
    rows: list[dict[str, Any]],
    ontology: Mapping[str, dict[str, Any]],
) -> None:
    missing = sorted(
        {
            str(row.get("metric_id"))
            for row in rows
            if str(row.get("metric_id")) not in ontology
        }
    )
    values = sorted(
        {
            _normalise(
                ontology.get(str(row.get("metric_id")), {}).get(field)
                or (
                    row.get("metric_period_type")
                    if field == "period_type"
                    else row.get(field)
                )
            )
            for row in rows
        }
    )
    check(
        f"same_{field}",
        not missing and len(values) <= 1,
        {"values": values, "missing_metrics": missing},
        {"values": "one ontology class", "missing_metrics": []},
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


def _result(checks: dict[str, dict[str, Any]]) -> SemanticValidationResult:
    errors = tuple(sorted(name for name, value in checks.items() if not value["passed"]))
    return SemanticValidationResult(not errors, errors, checks)


def _normalise(value: Any) -> str:
    return str(value or "").strip().lower()


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)
