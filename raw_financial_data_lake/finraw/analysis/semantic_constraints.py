from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from finraw.analysis.registry import FinancialSignalSpec
from finraw.qa.comparability import financial_scope_key

ANALYSIS_SEMANTIC_GATE_VERSION = "1.3.0"
_SUPPORTED_OPERATORS = {
    "contiguous",
    "same_within_series",
    "eq",
    "exact_coverage",
}


def validate_signal_semantics(
    spec: FinancialSignalSpec,
    role_facts: Mapping[str, list[dict[str, Any]]],
    *,
    target_entity_id: str | None = None,
) -> dict[str, Any]:
    checks: dict[str, dict[str, Any]] = {}
    errors: list[str] = []

    def add(name: str, passed: bool, observed: Any, expected: Any) -> None:
        checks[name] = {
            "passed": bool(passed),
            "observed": observed,
            "expected": expected,
        }
        if not passed:
            errors.append(name)

    expected_roles = set(spec.input_roles)
    observed_roles = set(role_facts)
    add(
        "analysis_signal_roles",
        observed_roles == expected_roles,
        sorted(observed_roles),
        sorted(expected_roles),
    )
    all_rows = [row for role in spec.input_roles for row in role_facts.get(role, [])]
    add(
        "analysis_signal_nonempty",
        bool(all_rows) and all(role_facts.get(role) for role in spec.input_roles),
        len(all_rows),
        "> 0 and every role nonempty",
    )
    add(
        "analysis_signal_graph_ready",
        bool(all_rows) and all(_truthy(row.get("graph_ready")) for row in all_rows),
        [row.get("graph_ready") for row in all_rows],
        "all true",
    )
    add(
        "analysis_signal_forecast",
        bool(all_rows) and all(not _truthy(row.get("is_forecast")) for row in all_rows),
        [row.get("is_forecast") for row in all_rows],
        "all false",
    )

    role_integrity: dict[str, Any] = {}
    role_ok = bool(all_rows)
    for role in spec.input_roles:
        rows = role_facts.get(role, [])
        facts = [str(row.get("fact_id") or "") for row in rows]
        metrics = {str(row.get("metric_id") or "") for row in rows}
        definitions = {str(row.get("source_definition_id") or "") for row in rows}
        definition_classes = {_source_definition_class(row) for row in rows}
        units = {str(row.get("normalized_unit") or "") for row in rows}
        currencies = {str(row.get("normalized_currency") or "") for row in rows}
        period_types = {str(row.get("metric_period_type") or "") for row in rows}
        expected_metric = str(spec.input_roles[role])
        metric_ok = expected_metric == "dynamic" or metrics == {expected_metric}
        peer_scope = (
            str(spec.required_scope.get("scope_type") or "")
            == "complete_industry_entity_set"
        )
        definition_ok = (
            len(definition_classes) == 1
            and all(value for value in next(iter(definition_classes), ()))
            if peer_scope
            else len(definitions) == 1 and "" not in definitions
        )
        current_ok = (
            bool(rows)
            and len(facts) == len(set(facts))
            and "" not in facts
            and metric_ok
            and definition_ok
            and len(units) == 1
            and "" not in units
            and len(currencies) == 1
            and "" not in currencies
            and len(period_types) == 1
            and "" not in period_types
        )
        role_ok = role_ok and current_ok
        role_integrity[role] = {
            "fact_count": len(rows),
            "metric_ids": sorted(metrics),
            "source_definition_ids": sorted(definitions),
            "source_definition_compatibility_classes": sorted(definition_classes),
            "units": sorted(units),
            "currencies": sorted(currencies),
            "metric_period_types": sorted(period_types),
            "passed": current_ok,
        }
    add(
        "analysis_signal_role_integrity",
        role_ok,
        role_integrity,
        "unique facts and one metric/definition/unit/currency/period type per role",
    )

    missing_defaults = dict(
        spec.required_scope.get("missing_field_defaults") or {}
    )
    for field in ("source_id", "frequency", "seasonal_adjustment", "vintage_policy"):
        values = {
            str(row.get(field) or missing_defaults.get(field) or "")
            for row in all_rows
        }
        add(
            f"analysis_signal_{field}",
            bool(values) and "" not in values and len(values) == 1,
            sorted(values),
            {
                "rule": "one nonempty value",
                "explicit_missing_default": missing_defaults.get(field),
            },
        )

    scope_pairs = {financial_scope_key(row) for row in all_rows}
    entity_scope_ok = bool(scope_pairs) and all(
        scope_id == str(row.get("entity_id") or "")
        and scope_type == "consolidated_entity"
        for row in all_rows
        for scope_id, scope_type in [financial_scope_key(row)]
    )
    add(
        "analysis_signal_financial_scope",
        entity_scope_ok,
        sorted(scope_pairs),
        "entity_scope_id matches entity_id; consolidated_entity",
    )

    required_scope_type = str(spec.required_scope.get("scope_type") or "")
    entities = {str(row.get("entity_id") or "") for row in all_rows}
    if required_scope_type == "canonical_consolidated_entity":
        add(
            "analysis_signal_entity_scope",
            len(entities) == 1 and "" not in entities,
            sorted(entities),
            "one canonical entity",
        )
    elif required_scope_type == "complete_industry_entity_set":
        role_entities = {
            role: {str(row.get("entity_id") or "") for row in role_facts.get(role, [])}
            for role in spec.input_roles
        }
        entity_sets = list(role_entities.values())
        same = (
            bool(entity_sets)
            and all(values == entity_sets[0] for values in entity_sets[1:])
            and "" not in entity_sets[0]
            and all(
                len(role_facts.get(role, [])) == len(entity_ids)
                for role, entity_ids in role_entities.items()
            )
        )
        add(
            "analysis_scope_gate",
            same,
            {
                key: {
                    "entity_ids": sorted(value),
                    "fact_count": len(role_facts.get(key, [])),
                }
                for key, value in role_entities.items()
            },
            "exact same entity set and one unique fact per entity across roles",
        )
        add(
            "analysis_scope_target",
            bool(target_entity_id)
            and target_entity_id in (entity_sets[0] if entity_sets else set()),
            target_entity_id,
            "target belongs to complete scope",
        )
        metric_role_groups: dict[str, list[str]] = {}
        for role, metric_id in spec.input_roles.items():
            metric_role_groups.setdefault(str(metric_id), []).append(role)
        definition_by_metric_entity: dict[str, dict[str, set[str]]] = {}
        for metric_id, roles in metric_role_groups.items():
            by_entity: dict[str, set[str]] = {}
            for role in roles:
                for row in role_facts.get(role, []):
                    by_entity.setdefault(str(row.get("entity_id") or ""), set()).add(
                        str(row.get("source_definition_id") or "")
                    )
            definition_by_metric_entity[metric_id] = by_entity
        definition_continuity = all(
            entity_id
            and len(definitions) == 1
            and "" not in definitions
            for by_entity in definition_by_metric_entity.values()
            for entity_id, definitions in by_entity.items()
        )
        add(
            "analysis_scope_source_definition_continuity",
            definition_continuity,
            {
                metric: {
                    entity: sorted(definitions)
                    for entity, definitions in by_entity.items()
                }
                for metric, by_entity in definition_by_metric_entity.items()
            },
            "each entity uses one SourceDefinition per metric across peer roles",
        )
    else:
        add(
            "analysis_signal_scope_type",
            False,
            required_scope_type,
            "registered scope type",
        )

    for constraint in spec.semantic_constraints:
        operator = str(constraint.get("operator") or "")
        field = str(constraint.get("field") or "")
        if operator not in _SUPPORTED_OPERATORS:
            add(
                f"analysis_constraint_unknown_{field}_{operator}",
                False,
                constraint,
                sorted(_SUPPORTED_OPERATORS),
            )
            continue
        if operator == "contiguous":
            observed = {role: _years(rows) for role, rows in role_facts.items()}
            passed = all(
                len(years) >= spec.required_periods
                and all(right - left == 1 for left, right in zip(years, years[1:]))
                for years in observed.values()
            )
        elif operator == "same_within_series":
            observed = {
                role: sorted(
                    {str(row.get("source_definition_id") or "") for row in rows}
                )
                for role, rows in role_facts.items()
            }
            passed = all(
                len(values) == 1 and values != [""] for values in observed.values()
            )
        elif operator == "eq" and field == "is_forecast":
            observed = [bool(_truthy(row.get("is_forecast"))) for row in all_rows]
            passed = bool(all_rows) and all(
                value == bool(constraint.get("value")) for value in observed
            )
        elif operator == "eq" and field == "scope_input_coverage":
            observed = {
                role: sorted({str(row.get("entity_id") or "") for row in rows})
                for role, rows in role_facts.items()
            }
            sets = [set(value) for value in observed.values()]
            passed = bool(sets) and all(value == sets[0] for value in sets[1:])
        elif operator == "exact_coverage":
            observed = {role: _years(rows) for role, rows in role_facts.items()}
            values = list(observed.values())
            passed = (
                bool(values)
                and all(value == values[0] for value in values[1:])
                and len(values[0]) >= spec.required_periods
            )
        else:
            observed = constraint
            passed = False
        add(
            f"analysis_constraint_{field}_{operator}",
            passed,
            observed,
            constraint.get("value", "constraint satisfied"),
        )

    return {
        "passed": not errors,
        "checks": checks,
        "errors": errors,
        "version": ANALYSIS_SEMANTIC_GATE_VERSION,
    }


def _source_definition_class(row: dict[str, Any]) -> tuple[str, ...]:
    return (
        str(row.get("source_id") or ""),
        str(
            row.get("source_definition_comparable_metric_id")
            or row.get("source_definition_metric_id")
            or row.get("metric_id")
            or ""
        ),
        str(row.get("source_definition_comparability_level") or row.get("comparability_level") or ""),
        str(row.get("source_definition_frequency") or row.get("frequency") or ""),
        str(row.get("source_definition_vintage_policy") or row.get("vintage_policy") or ""),
    )


def _years(rows: list[dict[str, Any]]) -> list[int]:
    values = []
    for row in rows:
        value = row.get("fiscal_year") or row.get("calendar_year")
        if value is None:
            return []
        values.append(int(value))
    return sorted(values)


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)
