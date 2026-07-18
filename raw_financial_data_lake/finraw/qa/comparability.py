from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Any


DEFAULT_ALLOWED_METRIC_PAIRS: tuple[tuple[str, str], ...] = (
    ("gross_profit", "operating_income"),
    ("operating_income", "net_income"),
    ("revenue", "gross_profit"),
    ("revenue", "net_income"),
    ("revenue", "operating_income"),
    ("total_assets", "total_liabilities"),
)

DEFAULT_FOLLOWUP_METRIC_PAIRS: tuple[tuple[str, str], ...] = (
    ("revenue", "net_income"),
    ("revenue", "operating_income"),
    ("revenue", "total_assets"),
    ("net_income", "operating_cash_flow"),
)

BLOCKED_COMPARABILITY_LEVELS = {
    "blocked",
    "incomparable",
    "not_comparable",
    "source_definition_mismatch",
}


def comparability_policy(config: dict[str, Any] | None = None) -> dict[str, Any]:
    configured = dict(config or {})
    scope_top_k = max(int(configured.get("scope_top_k", 3)), 1)
    growth_threshold = str(configured.get("growth_threshold_pct", 10))
    debt_ratio_threshold = str(configured.get("debt_ratio_max_pct", 70))
    return {
        "require_same_source": bool(configured.get("require_same_source", True)),
        "require_same_source_definition": bool(
            configured.get("require_same_source_definition", True)
        ),
        "require_same_entity_type": bool(
            configured.get("require_same_entity_type", True)
        ),
        "require_shared_company_industry": bool(
            configured.get("require_shared_company_industry", True)
        ),
        "require_same_time_basis": bool(
            configured.get("require_same_time_basis", True)
        ),
        "require_same_period_type": bool(
            configured.get("require_same_period_type", True)
        ),
        "require_same_frequency": bool(configured.get("require_same_frequency", True)),
        "require_same_seasonal_adjustment": bool(
            configured.get("require_same_seasonal_adjustment", True)
        ),
        "require_same_vintage_policy": bool(
            configured.get("require_same_vintage_policy", True)
        ),
        "require_same_financial_scope": bool(
            configured.get("require_same_financial_scope", True)
        ),
        "scope_min_entities": max(int(configured.get("scope_min_entities", 3)), 2),
        "scope_top_k": scope_top_k,
        "scope_top_ks": _integer_scenarios(
            configured.get("scope_top_ks"), scope_top_k, minimum=1
        ),
        "growth_threshold_pct": growth_threshold,
        "growth_thresholds_pct": _decimal_scenarios(
            configured.get("growth_thresholds_pct"), growth_threshold
        ),
        "debt_ratio_max_pct": debt_ratio_threshold,
        "debt_ratio_thresholds_pct": _decimal_scenarios(
            configured.get("debt_ratio_thresholds_pct"), debt_ratio_threshold
        ),
        "scope_scan_rows_per_metric": max(
            int(configured.get("scope_scan_rows_per_metric", 20000)), 100
        ),
        "allowed_metric_pairs": _normalise_pairs(
            configured.get("allowed_metric_pairs", DEFAULT_ALLOWED_METRIC_PAIRS)
        ),
        "followup_metric_pairs": _ordered_pairs(
            configured.get("followup_metric_pairs", DEFAULT_FOLLOWUP_METRIC_PAIRS)
        ),
        "temporal_frequencies": tuple(
            str(value).lower()
            for value in configured.get("temporal_frequencies", ["annual"])
        ),
        "temporal_metric_ids": tuple(
            str(value)
            for value in configured.get(
                "temporal_metric_ids",
                sorted(
                    {
                        metric
                        for pair in (
                            DEFAULT_ALLOWED_METRIC_PAIRS + DEFAULT_FOLLOWUP_METRIC_PAIRS
                        )
                        for metric in pair
                    }
                ),
            )
        ),
        "temporal_scan_rows_per_metric": max(
            int(configured.get("temporal_scan_rows_per_metric", 10000)), 100
        ),
        "pairwise_metric_ids": tuple(
            str(value)
            for value in configured.get(
                "pairwise_metric_ids",
                configured.get(
                    "temporal_metric_ids",
                    sorted(
                        {
                            metric
                            for pair in DEFAULT_ALLOWED_METRIC_PAIRS
                            for metric in pair
                        }
                    ),
                ),
            )
        ),
        "pairwise_scan_rows_per_metric": max(
            int(configured.get("pairwise_scan_rows_per_metric", 10000)), 100
        ),
        "temporal_min_observations": int(
            configured.get("temporal_min_observations", 3)
        ),
        "temporal_max_observations": int(
            configured.get("temporal_max_observations", 5)
        ),
        "require_contiguous_periods": bool(
            configured.get("require_contiguous_periods", True)
        ),
        "scan_multiplier": max(int(configured.get("scan_multiplier", 10)), 1),
        "max_per_stratum": max(int(configured.get("max_per_stratum", 4)), 1),
    }


def metric_pair_allowed(
    left_metric_id: str,
    right_metric_id: str,
    policy: dict[str, Any],
) -> bool:
    pair = tuple(sorted((str(left_metric_id), str(right_metric_id))))
    return pair in set(policy.get("allowed_metric_pairs") or ())


def facts_share_semantics(
    facts: Iterable[dict[str, Any]],
    *,
    require_same_definition: bool,
) -> tuple[bool, list[str]]:
    rows = list(facts)
    if not rows:
        return False, ["no_facts"]
    errors: list[str] = []
    if any(_truthy(row.get("is_forecast")) for row in rows):
        errors.append("forecast_input")
    for field in [
        "source_id",
        "time_basis",
        "metric_period_type",
        "frequency",
        "seasonal_adjustment",
        "vintage_policy",
    ]:
        if len({_normalised(row.get(field)) for row in rows}) > 1:
            errors.append(f"mixed_{field}")
    levels = {str(row.get("comparability_level") or "").strip().lower() for row in rows}
    if levels & BLOCKED_COMPARABILITY_LEVELS:
        errors.append("blocked_comparability_level")
    if (
        require_same_definition
        and len({_normalised(row.get("source_definition_id")) for row in rows}) > 1
    ):
        errors.append("mixed_source_definition")
    if len({financial_scope_key(row) for row in rows}) > 1:
        errors.append("mixed_financial_scope")
    return not errors, errors


def financial_scope_key(row: dict[str, Any]) -> tuple[str, str]:
    return (
        str(row.get("entity_scope_id") or row.get("entity_id") or ""),
        str(row.get("financial_scope_type") or "consolidated_entity"),
    )


def fact_frequency(row: dict[str, Any]) -> str:
    frequency = str(row.get("frequency") or "").strip().lower()
    if frequency in {"filing_period", "fiscal_period"}:
        quarter = str(row.get("fiscal_quarter") or "").upper()
        if quarter in {"Q1", "Q2", "Q3", "Q4"}:
            return "quarterly"
        if quarter == "FY" or row.get("fiscal_year"):
            return "annual"
    if frequency:
        return frequency
    if row.get("fiscal_year") or row.get("calendar_year"):
        quarter = str(row.get("fiscal_quarter") or "").upper()
        return "quarterly" if quarter in {"Q1", "Q2", "Q3", "Q4"} else "annual"
    return "observation"


def annual_duration_valid(row: dict[str, Any]) -> bool:
    if fact_frequency(row) != "annual":
        return True
    if str(row.get("metric_period_type") or "") == "point_in_time":
        return True
    start = _as_date(row.get("period_start"))
    end = _as_date(row.get("period_end"))
    if not start or not end:
        return False
    return 300 <= (end - start).days <= 430


def period_index(row: dict[str, Any], frequency: str | None = None) -> int | None:
    effective = (frequency or fact_frequency(row)).lower()
    year = row.get("fiscal_year") or row.get("calendar_year")
    if effective == "annual" and year is not None:
        return int(year)
    if effective == "quarterly" and year is not None:
        quarter = str(row.get("fiscal_quarter") or "").upper()
        order = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}
        return int(year) * 4 + order.get(quarter, 0) if quarter in order else None
    parsed = _as_date(row.get("period_end") or row.get("as_of_date"))
    if not parsed:
        return None
    if effective == "monthly":
        return parsed.year * 12 + parsed.month
    if effective == "daily":
        return parsed.toordinal()
    return parsed.toordinal()


def latest_contiguous_window(
    rows: Iterable[dict[str, Any]],
    *,
    frequency: str,
    minimum: int,
    maximum: int,
    require_contiguous: bool,
) -> list[dict[str, Any]]:
    by_period: dict[int, dict[str, Any]] = {}
    for row in rows:
        index = period_index(row, frequency)
        if index is None:
            continue
        current = by_period.get(index)
        if current is None or str(row.get("fact_id")) < str(current.get("fact_id")):
            by_period[index] = row
    ordered = sorted(by_period.items())
    if not ordered:
        return []
    runs: list[list[tuple[int, dict[str, Any]]]] = []
    run: list[tuple[int, dict[str, Any]]] = []
    for item in ordered:
        if require_contiguous and run and item[0] != run[-1][0] + 1:
            runs.append(run)
            run = []
        run.append(item)
    if run:
        runs.append(run)
    eligible = [run for run in runs if len(run) >= minimum]
    if not eligible:
        return []
    latest = max(eligible, key=lambda values: values[-1][0])[-maximum:]
    return [row for _, row in latest]


def period_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("time_basis"),
        row.get("fiscal_year"),
        row.get("fiscal_quarter"),
        row.get("calendar_year"),
        str(row.get("period_end") or row.get("as_of_date") or ""),
    )


def period_label(row: dict[str, Any]) -> str | int | None:
    year = row.get("fiscal_year") or row.get("calendar_year")
    quarter = str(row.get("fiscal_quarter") or "").upper()
    if year and quarter in {"Q1", "Q2", "Q3", "Q4"}:
        return f"{year} {quarter}"
    return year or row.get("period_end") or row.get("as_of_date")


def _integer_scenarios(values: Any, fallback: int, *, minimum: int) -> tuple[int, ...]:
    raw_values = values if isinstance(values, (list, tuple, set)) else [fallback]
    normalized = {max(int(value), minimum) for value in raw_values}
    return tuple(sorted(normalized or {fallback}))


def _decimal_scenarios(values: Any, fallback: str) -> tuple[str, ...]:
    from decimal import Decimal, InvalidOperation

    raw_values = values if isinstance(values, (list, tuple, set)) else [fallback]
    normalized = set()
    for value in raw_values:
        try:
            normalized.add(Decimal(str(value)))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid numeric scenario: {value!r}") from exc
    return tuple(str(value) for value in sorted(normalized or {Decimal(fallback)}))


def _normalise_pairs(values: Iterable[Iterable[Any]]) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted({tuple(sorted((str(left), str(right)))) for left, right in values})
    )


def _ordered_pairs(values: Iterable[Iterable[Any]]) -> tuple[tuple[str, str], ...]:
    return tuple((str(left), str(right)) for left, right in values)


def _normalised(value: Any) -> str:
    return str(value or "").strip().lower()


def _truthy(value: Any) -> bool:
    return value is True or str(value).strip().lower() in {"1", "true", "yes"}


def _as_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None
