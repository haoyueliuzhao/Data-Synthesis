from __future__ import annotations

from collections import defaultdict
from typing import Any

from finraw.db.client import DBProtocol
from finraw.qa.store import chunks


SUPPORTED_DISCOVERY_PATTERNS = {
    "pairwise_entity_metric_comparison",
    "entity_cross_metric_comparison",
    "entity_metric_temporal_average",
}


def discover_pattern_matches(
    db: DBProtocol,
    kg: dict[str, Any],
    pattern_id: str,
    *,
    limit: int,
) -> list[dict[str, Any]]:
    if pattern_id not in SUPPORTED_DISCOVERY_PATTERNS:
        raise ValueError(f"Pattern is registered but has no graph matcher: {pattern_id}")
    if limit <= 0:
        return []
    if pattern_id == "pairwise_entity_metric_comparison":
        return _pairwise_entity_matches(db, kg, limit)
    if pattern_id == "entity_cross_metric_comparison":
        return _cross_metric_matches(db, kg, limit)
    return _temporal_average_matches(db, kg, limit)


def _pairwise_entity_matches(
    db: DBProtocol, kg: dict[str, Any], limit: int
) -> list[dict[str, Any]]:
    rows = db.fetchall(
        """
        SELECT DISTINCT
               entity_left.source_pk AS left_entity_id,
               entity_right.source_pk AS right_entity_id,
               fact_left.source_pk AS left_fact_id,
               fact_right.source_pk AS right_fact_id,
               metric.source_pk AS metric_id,
               period.stable_node_id AS period_node_id
        FROM kg_edges has_left
        JOIN kg_nodes entity_left
          ON entity_left.node_id = has_left.src_node_id
         AND entity_left.kg_build_id = has_left.kg_build_id
         AND entity_left.node_type = 'Entity'
        JOIN kg_nodes fact_left
          ON fact_left.node_id = has_left.dst_node_id
         AND fact_left.kg_build_id = has_left.kg_build_id
         AND fact_left.node_type = 'Fact'
        JOIN kg_edges measures_left
          ON measures_left.src_node_id = fact_left.node_id
         AND measures_left.kg_build_id = fact_left.kg_build_id
         AND measures_left.relation_type = 'MEASURES'
        JOIN kg_nodes metric
          ON metric.node_id = measures_left.dst_node_id
         AND metric.kg_build_id = measures_left.kg_build_id
         AND metric.node_type = 'Metric'
        JOIN kg_edges period_left
          ON period_left.src_node_id = fact_left.node_id
         AND period_left.kg_build_id = fact_left.kg_build_id
         AND period_left.relation_type = 'IN_PERIOD'
        JOIN kg_nodes period
          ON period.node_id = period_left.dst_node_id
         AND period.kg_build_id = period_left.kg_build_id
         AND period.node_type = 'TimePeriod'
        JOIN kg_edges measures_right
          ON measures_right.dst_node_id = metric.node_id
         AND measures_right.kg_build_id = metric.kg_build_id
         AND measures_right.relation_type = 'MEASURES'
        JOIN kg_nodes fact_right
          ON fact_right.node_id = measures_right.src_node_id
         AND fact_right.kg_build_id = measures_right.kg_build_id
         AND fact_right.node_type = 'Fact'
        JOIN kg_edges period_right
          ON period_right.src_node_id = fact_right.node_id
         AND period_right.dst_node_id = period.node_id
         AND period_right.kg_build_id = fact_right.kg_build_id
         AND period_right.relation_type = 'IN_PERIOD'
        JOIN kg_edges has_right
          ON has_right.dst_node_id = fact_right.node_id
         AND has_right.kg_build_id = fact_right.kg_build_id
         AND has_right.relation_type = 'HAS_FACT'
        JOIN kg_nodes entity_right
          ON entity_right.node_id = has_right.src_node_id
         AND entity_right.kg_build_id = has_right.kg_build_id
         AND entity_right.node_type = 'Entity'
        JOIN standardized_facts sf_left
          ON sf_left.fact_id = fact_left.source_pk AND sf_left.build_id = ?
        JOIN standardized_facts sf_right
          ON sf_right.fact_id = fact_right.source_pk AND sf_right.build_id = ?
        WHERE has_left.kg_build_id = ?
          AND has_left.relation_type = 'HAS_FACT'
          AND entity_left.source_pk < entity_right.source_pk
          AND sf_left.normalized_value IS NOT NULL
          AND sf_right.normalized_value IS NOT NULL
          AND sf_left.normalized_unit = sf_right.normalized_unit
          AND COALESCE(sf_left.normalized_currency, '') = COALESCE(sf_right.normalized_currency, '')
        ORDER BY metric.source_pk, period.stable_node_id,
                 entity_left.source_pk, entity_right.source_pk
        LIMIT ?
        """,
        (kg["input_fact_build_id"], kg["input_fact_build_id"], kg["kg_build_id"], limit),
    )
    return [
        {
            "pattern_id": "pairwise_entity_metric_comparison",
            "input_bindings": {"left": row["left_fact_id"], "right": row["right_fact_id"]},
            "fact_ids": [str(row["left_fact_id"]), str(row["right_fact_id"])],
            "entity_ids": [str(row["left_entity_id"]), str(row["right_entity_id"])],
            "metric_ids": [str(row["metric_id"])],
            "period_node_id": str(row["period_node_id"]),
            "operator_params": {"id_field": "entity_id"},
        }
        for row in rows
    ]


def _cross_metric_matches(
    db: DBProtocol, kg: dict[str, Any], limit: int
) -> list[dict[str, Any]]:
    rows = db.fetchall(
        """
        SELECT DISTINCT
               entity.source_pk AS entity_id,
               fact_left.source_pk AS left_fact_id,
               fact_right.source_pk AS right_fact_id,
               metric_left.source_pk AS left_metric_id,
               metric_right.source_pk AS right_metric_id,
               period.stable_node_id AS period_node_id
        FROM kg_edges has_left
        JOIN kg_nodes entity
          ON entity.node_id = has_left.src_node_id
         AND entity.kg_build_id = has_left.kg_build_id
         AND entity.node_type = 'Entity'
        JOIN kg_nodes fact_left
          ON fact_left.node_id = has_left.dst_node_id
         AND fact_left.kg_build_id = has_left.kg_build_id
         AND fact_left.node_type = 'Fact'
        JOIN kg_edges measures_left
          ON measures_left.src_node_id = fact_left.node_id
         AND measures_left.kg_build_id = fact_left.kg_build_id
         AND measures_left.relation_type = 'MEASURES'
        JOIN kg_nodes metric_left
          ON metric_left.node_id = measures_left.dst_node_id
         AND metric_left.kg_build_id = measures_left.kg_build_id
         AND metric_left.node_type = 'Metric'
        JOIN kg_edges period_left
          ON period_left.src_node_id = fact_left.node_id
         AND period_left.kg_build_id = fact_left.kg_build_id
         AND period_left.relation_type = 'IN_PERIOD'
        JOIN kg_nodes period
          ON period.node_id = period_left.dst_node_id
         AND period.kg_build_id = period_left.kg_build_id
         AND period.node_type = 'TimePeriod'
        JOIN kg_edges has_right
          ON has_right.src_node_id = entity.node_id
         AND has_right.kg_build_id = entity.kg_build_id
         AND has_right.relation_type = 'HAS_FACT'
        JOIN kg_nodes fact_right
          ON fact_right.node_id = has_right.dst_node_id
         AND fact_right.kg_build_id = has_right.kg_build_id
         AND fact_right.node_type = 'Fact'
        JOIN kg_edges measures_right
          ON measures_right.src_node_id = fact_right.node_id
         AND measures_right.kg_build_id = fact_right.kg_build_id
         AND measures_right.relation_type = 'MEASURES'
        JOIN kg_nodes metric_right
          ON metric_right.node_id = measures_right.dst_node_id
         AND metric_right.kg_build_id = measures_right.kg_build_id
         AND metric_right.node_type = 'Metric'
        JOIN kg_edges period_right
          ON period_right.src_node_id = fact_right.node_id
         AND period_right.dst_node_id = period.node_id
         AND period_right.kg_build_id = fact_right.kg_build_id
         AND period_right.relation_type = 'IN_PERIOD'
        JOIN standardized_facts sf_left
          ON sf_left.fact_id = fact_left.source_pk AND sf_left.build_id = ?
        JOIN standardized_facts sf_right
          ON sf_right.fact_id = fact_right.source_pk AND sf_right.build_id = ?
        WHERE has_left.kg_build_id = ?
          AND has_left.relation_type = 'HAS_FACT'
          AND metric_left.source_pk < metric_right.source_pk
          AND sf_left.normalized_value IS NOT NULL
          AND sf_right.normalized_value IS NOT NULL
          AND sf_left.normalized_unit = sf_right.normalized_unit
          AND COALESCE(sf_left.normalized_currency, '') = COALESCE(sf_right.normalized_currency, '')
        ORDER BY entity.source_pk, period.stable_node_id,
                 metric_left.source_pk, metric_right.source_pk
        LIMIT ?
        """,
        (kg["input_fact_build_id"], kg["input_fact_build_id"], kg["kg_build_id"], limit),
    )
    return [
        {
            "pattern_id": "entity_cross_metric_comparison",
            "input_bindings": {"left": row["left_fact_id"], "right": row["right_fact_id"]},
            "fact_ids": [str(row["left_fact_id"]), str(row["right_fact_id"])],
            "entity_ids": [str(row["entity_id"])],
            "metric_ids": [str(row["left_metric_id"]), str(row["right_metric_id"])],
            "period_node_id": str(row["period_node_id"]),
            "operator_params": {"id_field": "metric_id"},
        }
        for row in rows
    ]


def _temporal_average_matches(
    db: DBProtocol, kg: dict[str, Any], limit: int
) -> list[dict[str, Any]]:
    scan_limit = max(limit * 20, 200)
    rows = db.fetchall(
        """
        SELECT DISTINCT entity.source_pk AS entity_id,
               fact.source_pk AS fact_id,
               metric.source_pk AS metric_id,
               period.stable_node_id AS period_node_id,
               sf.period_end, sf.fiscal_year, sf.calendar_year,
               sf.normalized_unit, sf.normalized_currency
        FROM kg_edges has_fact
        JOIN kg_nodes entity
          ON entity.node_id = has_fact.src_node_id
         AND entity.kg_build_id = has_fact.kg_build_id
         AND entity.node_type = 'Entity'
        JOIN kg_nodes fact
          ON fact.node_id = has_fact.dst_node_id
         AND fact.kg_build_id = has_fact.kg_build_id
         AND fact.node_type = 'Fact'
        JOIN kg_edges measures
          ON measures.src_node_id = fact.node_id
         AND measures.kg_build_id = fact.kg_build_id
         AND measures.relation_type = 'MEASURES'
        JOIN kg_nodes metric
          ON metric.node_id = measures.dst_node_id
         AND metric.kg_build_id = measures.kg_build_id
         AND metric.node_type = 'Metric'
        JOIN kg_edges in_period
          ON in_period.src_node_id = fact.node_id
         AND in_period.kg_build_id = fact.kg_build_id
         AND in_period.relation_type = 'IN_PERIOD'
        JOIN kg_nodes period
          ON period.node_id = in_period.dst_node_id
         AND period.kg_build_id = in_period.kg_build_id
         AND period.node_type = 'TimePeriod'
        JOIN standardized_facts sf
          ON sf.fact_id = fact.source_pk AND sf.build_id = ?
        WHERE has_fact.kg_build_id = ?
          AND has_fact.relation_type = 'HAS_FACT'
          AND sf.normalized_value IS NOT NULL
          AND sf.normalized_unit IS NOT NULL
        ORDER BY entity.source_pk, metric.source_pk, sf.period_end, fact.source_pk
        LIMIT ?
        """,
        (kg["input_fact_build_id"], kg["kg_build_id"], scan_limit),
    )
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (
            str(row["entity_id"]),
            str(row["metric_id"]),
            str(row["normalized_unit"]),
            str(row["normalized_currency"] or ""),
        )
        grouped[key].append(dict(row))
    matches: list[dict[str, Any]] = []
    for (entity_id, metric_id, _, _), series in sorted(grouped.items()):
        unique_periods: dict[str, dict[str, Any]] = {}
        for row in series:
            unique_periods.setdefault(str(row["period_node_id"]), row)
        ordered = sorted(
            unique_periods.values(),
            key=lambda row: (
                str(row.get("period_end") or ""),
                int(row.get("fiscal_year") or row.get("calendar_year") or 0),
                str(row.get("fact_id")),
            ),
        )
        if len(ordered) < 3:
            continue
        window = ordered[-5:]
        fact_ids = [str(row["fact_id"]) for row in window]
        matches.append(
            {
                "pattern_id": "entity_metric_temporal_average",
                "input_bindings": {"series": fact_ids},
                "fact_ids": fact_ids,
                "entity_ids": [entity_id],
                "metric_ids": [metric_id],
                "period_node_ids": [str(row["period_node_id"]) for row in window],
                "start_period": _period_value(window[0]),
                "end_period": _period_value(window[-1]),
            }
        )
        if len(matches) >= limit:
            break
    return matches


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


def _period_value(row: dict[str, Any]) -> str | int | None:
    return row.get("fiscal_year") or row.get("calendar_year") or row.get("period_end")
