from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from finraw.db.client import DBProtocol
from finraw.qa.comparability import (
    comparability_policy,
    fact_frequency,
    facts_share_semantics,
    latest_contiguous_window,
    period_index,
    period_label,
)
from finraw.qa.graph_patterns import get_pattern
from finraw.qa.store import chunks


Matcher = Callable[[DBProtocol, dict[str, Any], int, dict[str, Any]], list[dict[str, Any]]]
MATCHERS: dict[str, Matcher] = {}


def register_matcher(name: str) -> Callable[[Matcher], Matcher]:
    def decorator(function: Matcher) -> Matcher:
        if name in MATCHERS:
            raise RuntimeError(f"Duplicate QA graph matcher: {name}")
        MATCHERS[name] = function
        return function

    return decorator


def matcher_manifest() -> list[str]:
    return sorted(MATCHERS)


def discover_pattern_matches(
    db: DBProtocol,
    kg: dict[str, Any],
    pattern_id: str,
    *,
    limit: int,
    policy: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if limit <= 0:
        return []
    pattern = get_pattern(pattern_id)
    matcher_name = pattern.matcher
    if not matcher_name or matcher_name not in MATCHERS:
        raise ValueError(f"Pattern is registered but has no graph matcher: {pattern_id}")
    effective_policy = comparability_policy(policy)
    return MATCHERS[matcher_name](db, kg, limit, effective_policy)


@register_matcher("pairwise_entity_metric_comparison")
def match_pairwise_entities(
    db: DBProtocol,
    kg: dict[str, Any],
    limit: int,
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    return _match_pairwise_python_pool(db, kg, limit, policy)


def _match_pairwise_python_pool(
    db: DBProtocol,
    kg: dict[str, Any],
    limit: int,
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], dict[str, dict[str, Any]]] = defaultdict(dict)
    for metric_id in policy["pairwise_metric_ids"]:
        rows = db.fetchall(
            """
            SELECT sf.fact_id, sf.entity_id, sf.metric_id, sf.source_id,
                   sf.source_definition_id, sf.frequency, sf.time_basis,
                   sf.metric_period_type, sf.seasonal_adjustment,
                   sf.vintage_policy, sf.comparability_level,
                   sf.normalized_unit, sf.normalized_currency,
                   sf.fiscal_year, sf.fiscal_quarter, sf.calendar_year,
                   sf.period_end, sf.as_of_date,
                   ce.entity_type, ce.market, ce.country, ce.industry
            FROM standardized_facts sf
            JOIN kg_nodes fact_node
              ON fact_node.kg_build_id = ?
             AND fact_node.node_type = 'Fact'
             AND fact_node.source_pk = sf.fact_id
            JOIN canonical_entities ce
              ON ce.build_id = ? AND ce.entity_id = sf.entity_id
            WHERE sf.build_id = ? AND sf.metric_id = ?
              AND sf.graph_ready = 1
              AND sf.normalized_value IS NOT NULL
              AND sf.normalized_unit IS NOT NULL
              AND COALESCE(sf.is_forecast, 0) = 0
              AND LOWER(COALESCE(sf.comparability_level, 'comparable'))
                  NOT IN ('blocked', 'incomparable', 'not_comparable',
                          'source_definition_mismatch')
            ORDER BY sf.period_end DESC, sf.entity_id, sf.fact_id
            LIMIT ?
            """,
            (
                kg["kg_build_id"],
                kg["input_entity_build_id"],
                kg["input_fact_build_id"],
                metric_id,
                policy["pairwise_scan_rows_per_metric"],
            ),
        )
        for raw in rows:
            row = dict(raw)
            entity_type = str(row.get("entity_type") or "unknown")
            if entity_type == "company":
                scope_label = str(
                    row.get("industry") or row.get("market") or ""
                )
                if policy["require_shared_company_industry"] and not row.get(
                    "industry"
                ):
                    continue
            else:
                scope_label = str(row.get("country") or entity_type)
            key = (
                metric_id,
                _row_period_id(row),
                row.get("source_id"),
                row.get("source_definition_id")
                if policy["require_same_source_definition"]
                else row.get("comparability_level"),
                row.get("frequency"),
                row.get("time_basis"),
                row.get("metric_period_type"),
                row.get("seasonal_adjustment"),
                row.get("vintage_policy"),
                row.get("comparability_level"),
                row.get("normalized_unit"),
                row.get("normalized_currency"),
                entity_type,
                scope_label,
            )
            current = groups[key].get(str(row["entity_id"]))
            if current is None or str(row["fact_id"]) < str(current["fact_id"]):
                row["scope_label"] = scope_label
                groups[key][str(row["entity_id"])] = row
    candidates: list[dict[str, Any]] = []
    for key, by_entity in sorted(groups.items(), key=lambda item: str(item[0])):
        ordered = [by_entity[entity_id] for entity_id in sorted(by_entity)]
        for index in range(0, len(ordered) - 1, 2):
            left_row, right_row = ordered[index], ordered[index + 1]
            candidates.append(
                {
                    "pattern_id": "pairwise_entity_metric_comparison",
                    "input_bindings": {
                        "left": left_row["fact_id"],
                        "right": right_row["fact_id"],
                    },
                    "fact_ids": [
                        str(left_row["fact_id"]),
                        str(right_row["fact_id"]),
                    ],
                    "entity_ids": [
                        str(left_row["entity_id"]),
                        str(right_row["entity_id"]),
                    ],
                    "metric_ids": [str(left_row["metric_id"])],
                    "period_node_id": _row_period_id(left_row),
                    "frequency": fact_frequency(left_row),
                    "operator_params": {"id_field": "entity_id"},
                    "scope_type": "industry"
                    if left_row.get("entity_type") == "company"
                    else "entity_type",
                    "scope_definition": str(left_row["scope_label"]),
                    "comparability": _comparability_payload(left_row),
                    "sampling_stratum": [
                        left_row["metric_id"],
                        left_row["source_id"],
                        left_row["scope_label"],
                        _period_bucket(_row_period_id(left_row)),
                    ],
                }
            )
    return _stratified_take(candidates, limit, policy["max_per_stratum"])
@register_matcher("entity_cross_metric_comparison")
def match_cross_metrics(
    db: DBProtocol,
    kg: dict[str, Any],
    limit: int,
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    return _match_cross_metrics_python_join(db, kg, limit, policy)


def _match_cross_metrics_python_join(
    db: DBProtocol,
    kg: dict[str, Any],
    limit: int,
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    allowed_pairs = list(policy["allowed_metric_pairs"])
    if not allowed_pairs:
        return []
    scan_limit = max(limit * policy["scan_multiplier"] * 4, 500)
    ontology = {
        str(row["metric_id"]): dict(row)
        for row in db.fetchall(
            """
            SELECT metric_id, statement_type, period_type
            FROM metrics
            WHERE build_id = ?
            """,
            (kg["input_metric_build_id"],),
        )
    }
    metric_rows: dict[str, list[dict[str, Any]]] = {}
    for metric_id in sorted({metric for pair in allowed_pairs for metric in pair}):
        rows = db.fetchall(
            """
            SELECT sf.fact_id, sf.entity_id, sf.metric_id, sf.source_id,
                   sf.source_definition_id, sf.frequency, sf.time_basis,
                   sf.metric_period_type, sf.seasonal_adjustment,
                   sf.vintage_policy, sf.comparability_level,
                   sf.normalized_unit, sf.normalized_currency,
                   sf.fiscal_year, sf.fiscal_quarter, sf.calendar_year,
                   sf.period_end, sf.as_of_date
            FROM standardized_facts sf
            JOIN kg_nodes fact_node
              ON fact_node.kg_build_id = ?
             AND fact_node.node_type = 'Fact'
             AND fact_node.source_pk = sf.fact_id
            WHERE sf.build_id = ? AND sf.metric_id = ?
              AND sf.graph_ready = 1
              AND sf.normalized_value IS NOT NULL
              AND sf.normalized_unit IS NOT NULL
              AND COALESCE(sf.is_forecast, 0) = 0
              AND LOWER(COALESCE(sf.comparability_level, 'comparable'))
                  NOT IN ('blocked', 'incomparable', 'not_comparable',
                          'source_definition_mismatch')
            ORDER BY sf.period_end DESC, sf.entity_id, sf.fact_id
            LIMIT ?
            """,
            (
                kg["kg_build_id"],
                kg["input_fact_build_id"],
                metric_id,
                scan_limit,
            ),
        )
        canonical: dict[tuple[Any, ...], dict[str, Any]] = {}
        for raw in rows:
            row = dict(raw)
            key = (*_cross_metric_join_key(row), row.get("source_definition_id"))
            current = canonical.get(key)
            if current is None or str(row["fact_id"]) < str(current["fact_id"]):
                canonical[key] = row
        joinable: dict[tuple[Any, ...], dict[str, Any]] = {}
        for row in canonical.values():
            key = _cross_metric_join_key(row)
            current = joinable.get(key)
            if current is None or str(row.get("source_definition_id")) < str(
                current.get("source_definition_id")
            ):
                joinable[key] = row
        metric_rows[metric_id] = list(joinable.values())
    candidates: list[dict[str, Any]] = []
    for left_metric, right_metric in allowed_pairs:
        left_ontology = ontology.get(left_metric)
        right_ontology = ontology.get(right_metric)
        if not left_ontology or not right_ontology:
            continue
        if (
            str(left_ontology.get("period_type") or "")
            != str(right_ontology.get("period_type") or "")
            or str(left_ontology.get("statement_type") or "")
            != str(right_ontology.get("statement_type") or "")
        ):
            continue
        right_by_key = {
            _cross_metric_join_key(row): row
            for row in metric_rows.get(right_metric, [])
        }
        for left_row in metric_rows.get(left_metric, []):
            right_row = right_by_key.get(_cross_metric_join_key(left_row))
            if not right_row:
                continue
            period_node_id = _row_period_id(left_row)
            candidates.append(
                {
                    "pattern_id": "entity_cross_metric_comparison",
                    "input_bindings": {
                        "left": left_row["fact_id"],
                        "right": right_row["fact_id"],
                    },
                    "fact_ids": [
                        str(left_row["fact_id"]),
                        str(right_row["fact_id"]),
                    ],
                    "entity_ids": [str(left_row["entity_id"])],
                    "metric_ids": [left_metric, right_metric],
                    "period_node_id": period_node_id,
                    "frequency": fact_frequency(left_row),
                    "operator_params": {"id_field": "metric_id"},
                    "scope_type": "single_entity",
                    "scope_definition": str(left_row["entity_id"]),
                    "comparability": _comparability_payload(left_row),
                    "sampling_stratum": [
                        left_metric,
                        right_metric,
                        left_row["source_id"],
                        _period_bucket(period_node_id),
                    ],
                }
            )
    return _stratified_take(candidates, limit, policy["max_per_stratum"])


def _cross_metric_join_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("entity_id"),
        row.get("source_id"),
        row.get("frequency"),
        row.get("time_basis"),
        row.get("metric_period_type"),
        row.get("seasonal_adjustment"),
        row.get("vintage_policy"),
        row.get("comparability_level"),
        row.get("normalized_unit"),
        row.get("normalized_currency"),
        row.get("fiscal_year"),
        row.get("fiscal_quarter"),
        row.get("calendar_year"),
        str(row.get("period_end") or row.get("as_of_date") or ""),
    )


@register_matcher("entity_metric_temporal_average")
def match_temporal_average(
    db: DBProtocol,
    kg: dict[str, Any],
    limit: int,
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = _temporal_serving_rows(
        db,
        kg,
        policy=policy,
    )
    grouped = _group_temporal_rows(rows, include_metric=True)
    candidates = []
    for key, series in sorted(grouped.items(), key=lambda item: str(item[0])):
        entity_id, metric_id = str(key[0]), str(key[1])
        frequency = fact_frequency(series[0])
        if frequency not in policy["temporal_frequencies"]:
            continue
        compatible, _ = facts_share_semantics(series, require_same_definition=True)
        if not compatible:
            continue
        window = latest_contiguous_window(
            series,
            frequency=frequency,
            minimum=policy["temporal_min_observations"],
            maximum=policy["temporal_max_observations"],
            require_contiguous=policy["require_contiguous_periods"],
        )
        if len(window) < policy["temporal_min_observations"]:
            continue
        fact_ids = [str(row["fact_id"]) for row in window]
        candidates.append(
            {
                "pattern_id": "entity_metric_temporal_average",
                "input_bindings": {"series": fact_ids},
                "fact_ids": fact_ids,
                "entity_ids": [entity_id],
                "metric_ids": [metric_id],
                "period_node_ids": [_row_period_id(row) for row in window],
                "start_period": period_label(window[0]),
                "end_period": period_label(window[-1]),
                "observation_count": len(window),
                "frequency": frequency,
                "scope_type": "single_entity_time_series",
                "scope_definition": entity_id,
                "comparability": _comparability_payload(window[0]),
                "sampling_stratum": [
                    metric_id,
                    window[0].get("source_id"),
                    frequency,
                    entity_id,
                ],
            }
        )
    return _stratified_take(candidates, limit, policy["max_per_stratum"])


@register_matcher("temporal_argmax_then_metric_lookup")
def match_temporal_argmax_followup(
    db: DBProtocol,
    kg: dict[str, Any],
    limit: int,
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    metric_pairs = list(policy["followup_metric_pairs"])
    metric_ids = sorted({metric for pair in metric_pairs for metric in pair})
    rows = _temporal_serving_rows(
        db,
        kg,
        metric_ids=metric_ids,
        policy=policy,
    )
    by_entity_metric: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (
            row.get("entity_id"),
            row.get("metric_id"),
            row.get("source_id"),
            row.get("source_definition_id"),
            fact_frequency(row),
            row.get("time_basis"),
            row.get("metric_period_type"),
            row.get("normalized_unit"),
            row.get("normalized_currency"),
            row.get("seasonal_adjustment"),
            row.get("vintage_policy"),
            row.get("comparability_level"),
        )
        by_entity_metric[key].append(row)
    candidates = []
    for primary_metric, secondary_metric in metric_pairs:
        primary_groups = [
            (key, values)
            for key, values in by_entity_metric.items()
            if key[1] == primary_metric
        ]
        for key, primary_rows in primary_groups:
            (
                entity_id,
                _,
                source_id,
                primary_definition,
                frequency,
                time_basis,
                period_type,
                primary_unit,
                primary_currency,
                seasonal,
                vintage,
                level,
            ) = key
            if frequency not in policy["temporal_frequencies"]:
                continue
            compatible_secondary_groups = [
                (secondary_key, values)
                for secondary_key, values in by_entity_metric.items()
                if secondary_key[0] == entity_id
                and secondary_key[1] == secondary_metric
                and secondary_key[2] == source_id
                and secondary_key[4] == frequency
                and secondary_key[5] == time_basis
                and secondary_key[6] == period_type
                and secondary_key[9] == seasonal
                and secondary_key[10] == vintage
                and secondary_key[11] == level
            ]
            if not compatible_secondary_groups:
                continue
            primary_window = latest_contiguous_window(
                primary_rows,
                frequency=frequency,
                minimum=policy["temporal_min_observations"],
                maximum=policy["temporal_max_observations"],
                require_contiguous=policy["require_contiguous_periods"],
            )
            if len(primary_window) < policy["temporal_min_observations"]:
                continue
            for secondary_key, secondary_rows in compatible_secondary_groups:
                compatible, _ = facts_share_semantics(
                    secondary_rows, require_same_definition=True
                )
                if not compatible:
                    continue
                secondary_by_period = {
                    period_index(row, frequency): row for row in secondary_rows
                }
                secondary_window = [
                    secondary_by_period.get(period_index(row, frequency))
                    for row in primary_window
                ]
                if any(row is None for row in secondary_window):
                    continue
                bound_secondary = [row for row in secondary_window if row is not None]
                primary_ids = [str(row["fact_id"]) for row in primary_window]
                secondary_ids = [str(row["fact_id"]) for row in bound_secondary]
                candidate = {
                    "pattern_id": "temporal_argmax_then_metric_lookup",
                    "input_bindings": {
                        "primary_series": primary_ids,
                        "secondary_series": secondary_ids,
                    },
                    "fact_ids": primary_ids + secondary_ids,
                    "entity_ids": [str(entity_id)],
                    "metric_ids": [primary_metric, secondary_metric],
                    "start_period": period_label(primary_window[0]),
                    "end_period": period_label(primary_window[-1]),
                    "observation_count": len(primary_window),
                    "frequency": frequency,
                    "primary_metric_id": primary_metric,
                    "secondary_metric_id": secondary_metric,
                    "operator_params": {"frequency": frequency},
                    "scope_type": "single_entity_time_series_join",
                    "scope_definition": str(entity_id),
                    "comparability": _comparability_payload(primary_window[0]),
                    "series_definitions": {
                        "primary": primary_definition,
                        "secondary": secondary_key[3],
                    },
                    "series_units": {
                        "primary": [primary_unit, primary_currency],
                        "secondary": [secondary_key[7], secondary_key[8]],
                    },
                    "sampling_stratum": [
                        primary_metric,
                        secondary_metric,
                        source_id,
                        entity_id,
                    ],
                }
                candidates.append(candidate)
    return _stratified_take(candidates, limit, policy["max_per_stratum"])


def load_bound_facts(
    db: DBProtocol, fact_build_id: str, fact_ids: list[str]
) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for batch in chunks(sorted(set(fact_ids)), 500):
        placeholders = ",".join("?" for _ in batch)
        rows = db.fetchall(
            f"SELECT * FROM standardized_facts WHERE build_id = ? AND fact_id IN ({placeholders})",
            [fact_build_id, *batch],
        )
        output.update({str(row["fact_id"]): dict(row) for row in rows})
    return output


def _temporal_serving_rows(
    db: DBProtocol,
    kg: dict[str, Any],
    *,
    policy: dict[str, Any],
    metric_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    selected_metrics = list(metric_ids or policy["temporal_metric_ids"])
    rows: list[dict[str, Any]] = []
    for metric_id in selected_metrics:
        fetched = db.fetchall(
            """
            SELECT sf.entity_id, sf.fact_id, sf.metric_id,
                   sf.period_start, sf.period_end, sf.as_of_date,
                   sf.fiscal_year, sf.fiscal_quarter, sf.calendar_year,
                   sf.normalized_unit, sf.normalized_currency,
                   sf.source_id, sf.source_definition_id, sf.frequency,
                   sf.time_basis, sf.metric_period_type,
                   sf.seasonal_adjustment, sf.vintage_policy,
                   sf.comparability_level, sf.is_forecast
            FROM standardized_facts sf
            JOIN kg_nodes fact_node
              ON fact_node.kg_build_id = ?
             AND fact_node.node_type = 'Fact'
             AND fact_node.source_pk = sf.fact_id
            WHERE sf.build_id = ? AND sf.metric_id = ?
              AND sf.graph_ready = 1
              AND sf.normalized_value IS NOT NULL
              AND sf.normalized_unit IS NOT NULL
              AND COALESCE(sf.is_forecast, 0) = 0
              AND LOWER(COALESCE(sf.comparability_level, 'comparable'))
                  NOT IN ('blocked', 'incomparable', 'not_comparable',
                          'source_definition_mismatch')
            ORDER BY sf.entity_id, sf.period_end DESC, sf.fact_id
            LIMIT ?
            """,
            (
                kg["kg_build_id"],
                kg["input_fact_build_id"],
                metric_id,
                policy["temporal_scan_rows_per_metric"],
            ),
        )
        rows.extend(dict(row) for row in fetched)
    return rows


def _group_temporal_rows(
    rows: list[dict[str, Any]], *, include_metric: bool
) -> dict[tuple[Any, ...], list[dict[str, Any]]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (
            row.get("entity_id"),
            row.get("metric_id") if include_metric else None,
            row.get("source_id"),
            row.get("source_definition_id"),
            fact_frequency(row),
            row.get("time_basis"),
            row.get("metric_period_type"),
            row.get("normalized_unit"),
            row.get("normalized_currency"),
            row.get("seasonal_adjustment"),
            row.get("vintage_policy"),
            row.get("comparability_level"),
        )
        grouped[key].append(row)
    return grouped


def _stratified_take(
    candidates: list[dict[str, Any]], limit: int, max_per_stratum: int
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        key = tuple(str(value) for value in candidate.get("sampling_stratum") or ["default"])
        groups[key].append(candidate)
    for rows in groups.values():
        rows.sort(key=_candidate_hash)
    selected: list[dict[str, Any]] = []
    for index in range(max_per_stratum):
        for key in sorted(groups, key=_stratum_hash):
            if index < len(groups[key]):
                selected.append(groups[key][index])
                if len(selected) >= limit:
                    return selected
    return selected


def _candidate_hash(candidate: dict[str, Any]) -> str:
    payload = "|".join(sorted(str(value) for value in candidate.get("fact_ids") or []))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _stratum_hash(key: tuple[str, ...]) -> str:
    return hashlib.sha1("|".join(key).encode("utf-8")).hexdigest()


def _comparability_payload(row: Any) -> dict[str, Any]:
    payload = dict(row)
    return {
        "source_id": payload.get("source_id"),
        "source_definition_id": payload.get("source_definition_id"),
        "frequency": payload.get("frequency") or fact_frequency(payload),
        "time_basis": payload.get("time_basis"),
        "metric_period_type": payload.get("metric_period_type"),
        "seasonal_adjustment": payload.get("seasonal_adjustment"),
        "vintage_policy": payload.get("vintage_policy"),
        "comparability_level": payload.get("comparability_level"),
        "entity_type": payload.get("entity_type"),
        "is_forecast": False,
    }


def _period_bucket(value: Any) -> str:
    text = str(value or "")
    digits = "".join(character for character in text if character.isdigit())
    return digits[:4] if len(digits) >= 4 else text


def _row_period_id(row: dict[str, Any]) -> str:
    year = row.get("fiscal_year") or row.get("calendar_year")
    quarter = str(row.get("fiscal_quarter") or "").upper()
    if year and quarter in {"Q1", "Q2", "Q3", "Q4", "FY"}:
        return f"{year}-{quarter}"
    return str(row.get("period_end") or year or "unknown-period")
