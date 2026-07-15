from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any

from finraw.db.client import DBProtocol
from finraw.qa.comparability import annual_duration_valid, financial_scope_key
from finraw.qa.graph_matcher import _stratified_take, register_matcher


@register_matcher("industry_growth_filter_then_margin_rank")
def match_industry_filter_rank(
    db: DBProtocol,
    kg: dict[str, Any],
    limit: int,
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    scopes = _scope_financial_groups(db, kg, policy)
    top_k = policy["scope_top_k"]
    threshold = Decimal(policy["growth_threshold_pct"])
    candidates = []
    for key, current in sorted(scopes.items(), key=lambda item: str(item[0])):
        industry, year, source_id, unit, currency = key
        previous = scopes.get((industry, year - 1, source_id, unit, currency), {})
        complete = _complete_scope_entities(
            current, previous, {"revenue", "net_income"}
        )
        qualifying = [
            entity_id
            for entity_id in complete
            if _growth_pct(
                current[entity_id]["revenue"], previous[entity_id]["revenue"]
            )
            > threshold
        ]
        if len(complete) < policy["scope_min_entities"] or len(qualifying) < top_k:
            continue
        bindings = {
            "current_revenue": _fact_ids(complete, current, "revenue"),
            "previous_revenue": _fact_ids(complete, previous, "revenue"),
            "net_income": _fact_ids(complete, current, "net_income"),
        }
        candidates.append(
            _scope_match(
                "industry_growth_filter_then_margin_rank",
                bindings,
                complete,
                ["revenue", "net_income"],
                industry,
                year,
                source_id,
                {
                    "growth_filter": {"value": str(threshold)},
                    "answer": {"top_k": top_k},
                },
                [industry, year, "filter_rank"],
            )
        )
    return _stratified_take(candidates, limit, policy["max_per_stratum"])


@register_matcher("industry_revenue_rank_then_assets_lookup")
def match_industry_rank_lookup(
    db: DBProtocol,
    kg: dict[str, Any],
    limit: int,
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    scopes = _scope_financial_groups(db, kg, policy)
    top_k = policy["scope_top_k"]
    candidates = []
    for key, current in sorted(scopes.items(), key=lambda item: str(item[0])):
        industry, year, source_id, _, _ = key
        complete = sorted(
            entity_id
            for entity_id, metrics in current.items()
            if {"revenue", "total_assets"}.issubset(metrics)
            and _ratio_compatible(metrics["revenue"], metrics["total_assets"])
        )
        if len(complete) < max(policy["scope_min_entities"], top_k):
            continue
        bindings = {
            "revenue": _fact_ids(complete, current, "revenue"),
            "total_assets": _fact_ids(complete, current, "total_assets"),
        }
        candidates.append(
            _scope_match(
                "industry_revenue_rank_then_assets_lookup",
                bindings,
                complete,
                ["revenue", "total_assets"],
                industry,
                year,
                source_id,
                {"rank_revenue": {"top_k": top_k}},
                [industry, year, "rank_lookup"],
            )
        )
    return _stratified_take(candidates, limit, policy["max_per_stratum"])


@register_matcher("industry_multi_factor_screening")
def match_industry_multi_factor(
    db: DBProtocol,
    kg: dict[str, Any],
    limit: int,
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    scopes = _scope_financial_groups(db, kg, policy)
    growth_min = Decimal(policy["growth_threshold_pct"])
    debt_max = Decimal(policy["debt_ratio_max_pct"])
    candidates = []
    for key, current in sorted(scopes.items(), key=lambda item: str(item[0])):
        industry, year, source_id, unit, currency = key
        previous = scopes.get((industry, year - 1, source_id, unit, currency), {})
        complete = _complete_scope_entities(
            current,
            previous,
            {"revenue", "net_income", "total_assets", "total_liabilities"},
        )
        if len(complete) < policy["scope_min_entities"]:
            continue
        margins = {
            entity_id: _ratio_pct(
                current[entity_id]["net_income"], current[entity_id]["revenue"]
            )
            for entity_id in complete
        }
        average_margin = sum(margins.values(), Decimal("0")) / Decimal(len(margins))
        selected = [
            entity_id
            for entity_id in complete
            if _growth_pct(
                current[entity_id]["revenue"], previous[entity_id]["revenue"]
            )
            > growth_min
            and margins[entity_id] > average_margin
            and _ratio_pct(
                current[entity_id]["total_liabilities"],
                current[entity_id]["total_assets"],
            )
            < debt_max
        ]
        if not selected:
            continue
        bindings = {
            "current_revenue": _fact_ids(complete, current, "revenue"),
            "previous_revenue": _fact_ids(complete, previous, "revenue"),
            "net_income": _fact_ids(complete, current, "net_income"),
            "total_assets": _fact_ids(complete, current, "total_assets"),
            "total_liabilities": _fact_ids(complete, current, "total_liabilities"),
        }
        candidates.append(
            _scope_match(
                "industry_multi_factor_screening",
                bindings,
                complete,
                ["revenue", "net_income", "total_assets", "total_liabilities"],
                industry,
                year,
                source_id,
                {
                    "answer": {
                        "growth_min_pct": str(growth_min),
                        "debt_max_pct": str(debt_max),
                    }
                },
                [industry, year, "multi_factor"],
            )
        )
    return _stratified_take(candidates, limit, policy["max_per_stratum"])


def _scope_financial_groups(
    db: DBProtocol, kg: dict[str, Any], policy: dict[str, Any]
) -> dict[tuple[Any, ...], dict[str, dict[str, dict[str, Any]]]]:
    groups: dict[tuple[Any, ...], dict[str, dict[str, dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    for metric_id in ("revenue", "net_income", "total_assets", "total_liabilities"):
        rows = db.fetchall(
            """
            SELECT sf.fact_id, sf.entity_id, sf.entity_scope_id,
                   sf.financial_scope_type, sf.metric_id, sf.normalized_value,
                   sf.normalized_unit, sf.normalized_currency, sf.fiscal_year,
                   sf.fiscal_quarter, sf.period_start, sf.period_end, sf.report_date,
                   sf.source_id, sf.source_definition_id, sf.frequency,
                   sf.time_basis, sf.metric_period_type, sf.verification_status,
                   sf.confidence_score, ce.industry, ce.entity_type
            FROM standardized_facts sf
            JOIN kg_nodes fact_node
              ON fact_node.kg_build_id = ? AND fact_node.node_type = 'Fact'
             AND fact_node.source_pk = sf.fact_id
            JOIN canonical_entities ce
              ON ce.build_id = ? AND ce.entity_id = sf.entity_id
            WHERE sf.build_id = ? AND sf.metric_id = ?
              AND sf.graph_ready = 1 AND sf.normalized_value IS NOT NULL
              AND sf.normalized_unit IS NOT NULL AND sf.fiscal_year IS NOT NULL
              AND UPPER(COALESCE(sf.fiscal_quarter, '')) = 'FY'
              AND ce.entity_type = 'company' AND ce.industry IS NOT NULL
              AND COALESCE(sf.is_forecast, 0) = 0
            ORDER BY sf.fiscal_year DESC, ce.industry, sf.entity_id, sf.fact_id
            LIMIT ?
            """,
            (
                kg["kg_build_id"],
                kg["input_entity_build_id"],
                kg["input_fact_build_id"],
                metric_id,
                policy["scope_scan_rows_per_metric"],
            ),
        )
        for raw in rows:
            row = dict(raw)
            if not annual_duration_valid(row):
                continue
            if financial_scope_key(row) != (
                str(row.get("entity_id")),
                "consolidated_entity",
            ):
                continue
            key = (
                str(row["industry"]),
                int(row["fiscal_year"]),
                str(row["source_id"]),
                row.get("normalized_unit"),
                row.get("normalized_currency"),
            )
            entity_metrics = groups[key][str(row["entity_id"])]
            current = entity_metrics.get(metric_id)
            if current is None or _scope_row_score(row) > _scope_row_score(current):
                entity_metrics[metric_id] = row
    return groups


def _complete_scope_entities(
    current: dict[str, dict[str, dict[str, Any]]],
    previous: dict[str, dict[str, dict[str, Any]]],
    required_current: set[str],
) -> list[str]:
    complete = []
    for entity_id in sorted(set(current) & set(previous)):
        current_metrics = current[entity_id]
        previous_metrics = previous[entity_id]
        if not required_current.issubset(current_metrics) or "revenue" not in previous_metrics:
            continue
        if current_metrics["revenue"].get("source_definition_id") != previous_metrics["revenue"].get("source_definition_id"):
            continue
        if not _ratio_compatible(
            current_metrics["revenue"], previous_metrics["revenue"]
        ):
            continue
        if "net_income" in required_current and not _ratio_compatible(
            current_metrics["net_income"], current_metrics["revenue"]
        ):
            continue
        if {"total_assets", "total_liabilities"}.issubset(
            required_current
        ) and not _ratio_compatible(
            current_metrics["total_liabilities"], current_metrics["total_assets"]
        ):
            continue
        if _decimal_value(previous_metrics["revenue"]) == 0:
            continue
        if (
            "total_assets" in required_current
            and _decimal_value(current_metrics["total_assets"]) == 0
        ):
            continue
        complete.append(entity_id)
    return complete


def _scope_match(
    pattern_id: str,
    bindings: dict[str, list[str]],
    entity_ids: list[str],
    metric_ids: list[str],
    industry: str,
    year: int,
    source_id: str,
    operator_step_params: dict[str, dict[str, Any]],
    stratum: list[Any],
) -> dict[str, Any]:
    fact_ids = sorted({fact_id for values in bindings.values() for fact_id in values})
    return {
        "pattern_id": pattern_id,
        "input_bindings": bindings,
        "fact_ids": fact_ids,
        "entity_ids": entity_ids,
        "metric_ids": metric_ids,
        "period": year,
        "frequency": "annual",
        "scope_type": "canonical_industry_complete_case",
        "scope_definition": (
            f"the canonical '{industry}' industry complete-case universe "
            f"({len(entity_ids)} companies with consolidated comparable inputs)"
        ),
        "industry": industry,
        "source_id": source_id,
        "operator_step_params": operator_step_params,
        "financial_scope": {
            "financial_scope_type": "consolidated_entity",
            "entity_scope_ids": entity_ids,
        },
        "sampling_stratum": [str(value) for value in stratum],
    }


def _fact_ids(
    entity_ids: list[str],
    rows: dict[str, dict[str, dict[str, Any]]],
    metric_id: str,
) -> list[str]:
    return [str(rows[entity_id][metric_id]["fact_id"]) for entity_id in entity_ids]


def _ratio_compatible(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return (
        left.get("normalized_unit") == right.get("normalized_unit")
        and left.get("normalized_currency") == right.get("normalized_currency")
        and financial_scope_key(left) == financial_scope_key(right)
    )


def _growth_pct(current: dict[str, Any], previous: dict[str, Any]) -> Decimal:
    prior = _decimal_value(previous)
    return ((_decimal_value(current) - prior) / abs(prior)) * Decimal("100")


def _ratio_pct(numerator: dict[str, Any], denominator: dict[str, Any]) -> Decimal:
    return (_decimal_value(numerator) / _decimal_value(denominator)) * Decimal("100")


def _decimal_value(row: dict[str, Any]) -> Decimal:
    try:
        return Decimal(str(row.get("normalized_value")))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid scope fact value: {row.get('fact_id')}") from exc


def _scope_row_score(row: dict[str, Any]) -> tuple[int, float, str, str]:
    return (
        2 if row.get("verification_status") == "cross_verified" else 1,
        float(row.get("confidence_score") or 0),
        str(row.get("report_date") or ""),
        str(row.get("fact_id") or ""),
    )
