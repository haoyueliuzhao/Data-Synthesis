from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from finraw.db.client import DBProtocol


SUMMARY_COLUMNS = [
    "source_id",
    "entity_count",
    "metric_count",
    "min_date",
    "max_date",
    "object_count",
    "missing_rate",
    "parse_ready",
    "quality_level",
]

SOURCE_DATA_TYPES = {
    "sec_companyfacts": ["company_fundamentals", "xbrl_companyfacts", "financial_statement_facts"],
    "sec_submissions": ["filing_history", "company_registry"],
    "sec_filings": ["filing_documents", "10-K", "10-Q", "8-K", "html"],
    "fred_observations": ["macro_timeseries", "rates", "employment", "inflation", "fx"],
    "worldbank_indicators": ["country_macro", "development_indicators", "annual_observations"],
    "imf_sdmx": ["international_macro", "imf_datamapper_raw_json"],
    "cninfo_announcements": ["cn_company_announcements", "reports_pdf", "financial_statement_facts"],
    "bse_disclosures": ["cn_company_announcements", "annual_reports_pdf", "financial_statement_facts"],
    "hkex_disclosures": ["hk_company_announcements", "annual_reports_pdf", "financial_statement_facts"],
    "nbs_official_statistics": ["cn_macro_statistics", "official_publications"],
    "pboc_official_statistics": ["cn_money_credit_rates", "official_publications"],
    "safe_official_statistics": ["cn_fx_external_sector", "official_publications"],
    "sse_market_statistics": ["cn_exchange_market_statistics", "official_publications"],
    "szse_market_statistics": ["cn_exchange_market_statistics", "official_publications"],
    "bse_market_statistics": ["cn_exchange_market_statistics", "official_publications"],
    "csi_index_publications": ["cn_index_publications", "official_publications"],
    "exchange_announcements": ["exchange_announcements"],
}

SOURCE_ENTITY_TYPES = {
    "sec_companyfacts": ["company"],
    "sec_submissions": ["company"],
    "sec_filings": ["company"],
    "fred_observations": ["macro_series", "rates", "fx_series"],
    "worldbank_indicators": ["country", "region", "indicator"],
    "imf_sdmx": ["country", "region", "indicator"],
    "cninfo_announcements": ["cn_company"],
    "bse_disclosures": ["cn_company"],
    "hkex_disclosures": ["hk_listed_company"],
    "nbs_official_statistics": ["country", "macro_series"],
    "pboc_official_statistics": ["country", "macro_series"],
    "safe_official_statistics": ["country", "macro_series", "currency_pair"],
    "sse_market_statistics": ["exchange", "market_series"],
    "szse_market_statistics": ["exchange", "market_series"],
    "bse_market_statistics": ["exchange", "market_series"],
    "csi_index_publications": ["index"],
    "exchange_announcements": ["company"],
}

PARSE_READY = {
    "sec_companyfacts": True,
    "sec_submissions": True,
    "sec_filings": False,
    "fred_observations": True,
    "worldbank_indicators": True,
    "imf_sdmx": False,
    "cninfo_announcements": True,
    "bse_disclosures": True,
    "hkex_disclosures": True,
    "exchange_announcements": False,
}


def refresh_data_coverage_report(db: DBProtocol, config: dict[str, Any], output_dir: str | None = None) -> dict[str, Any]:
    report = build_data_coverage_report(db, config)
    db.execute("DELETE FROM data_coverage_report")
    for row in report["data_coverage_report"]:
        db.execute(
            """
            INSERT INTO data_coverage_report (
                source_id, entity_count, metric_count, min_date, max_date,
                object_count, missing_rate, parse_ready, quality_level
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [row.get(column) for column in SUMMARY_COLUMNS],
        )
    if output_dir:
        write_coverage_outputs(report, output_dir)
    return report


def build_data_coverage_report(db: DBProtocol, config: dict[str, Any]) -> dict[str, Any]:
    registry_rows = [dict(row) for row in db.fetchall("SELECT * FROM source_registry")]
    object_rows = [dict(row) for row in db.fetchall("SELECT * FROM raw_objects")]
    record_rows = [dict(row) for row in db.fetchall("SELECT * FROM raw_records")]
    entity_rows = [dict(row) for row in db.fetchall("SELECT * FROM source_entities")]
    job_rows = [dict(row) for row in db.fetchall("SELECT * FROM ingestion_jobs")]
    active_fact_summaries = _active_fact_summaries(db)

    source_ids = sorted(
        {row["source_id"] for row in registry_rows}
        | {row["source_id"] for row in object_rows}
        | {row["source_id"] for row in record_rows}
        | set(active_fact_summaries)
        | {"exchange_announcements"}
    )
    registry_by_source = {row["source_id"]: row for row in registry_rows}
    objects_by_source = _group_by(object_rows, "source_id")
    records_by_source = _group_by(record_rows, "source_id")
    entities_by_source = _group_by(entity_rows, "source_id")
    jobs_by_source = _group_by(job_rows, "source_id")

    source_reports: dict[str, dict[str, Any]] = {}
    for source_id in source_ids:
        source_reports[source_id] = _base_source_report(
            source_id,
            registry_by_source.get(source_id, {}),
            objects_by_source.get(source_id, []),
            records_by_source.get(source_id, []),
            entities_by_source.get(source_id, []),
            jobs_by_source.get(source_id, []),
            active_fact_summaries.get(source_id, {}),
        )

    _audit_sec_companyfacts(source_reports.get("sec_companyfacts"), config)
    _audit_sec_submissions(source_reports.get("sec_submissions"), config)
    _audit_sec_filings(source_reports.get("sec_filings"), config)
    _audit_fred(source_reports.get("fred_observations"), config)
    _audit_worldbank(source_reports.get("worldbank_indicators"), config)
    _audit_imf(source_reports.get("imf_sdmx"), config)
    _audit_cninfo(source_reports.get("cninfo_announcements"), config)
    _audit_exchange_announcements(source_reports.get("exchange_announcements"))
    for source_report in source_reports.values():
        _set_quality(source_report)

    summary_rows = [_summary_row(source_reports[source_id]) for source_id in source_ids]
    return {
        "report_generated_at": date.today().isoformat(),
        "data_sources": _data_sources(source_reports),
        "entity_inventory": _entity_inventory(source_reports),
        "data_type_inventory": _data_type_inventory(source_reports),
        "data_coverage_report": summary_rows,
        "source_reports": [source_reports[source_id] for source_id in source_ids],
        "recommended_build_order": [
            "sec_companyfacts",
            "fred_observations",
            "worldbank_indicators",
            "sec_submissions",
            "sec_filings",
            "cninfo_announcements",
            "imf_sdmx",
            "exchange_announcements",
        ],
    }


def write_coverage_outputs(report: dict[str, Any], output_dir: str) -> list[Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "data_coverage_report.json"
    md_path = out / "data_coverage_report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    md_path.write_text(_markdown_report(report), encoding="utf-8")
    return [json_path, md_path]


def _active_fact_summaries(db: DBProtocol) -> dict[str, dict[str, Any]]:
    rows = db.fetchall(
        "SELECT source_id, COUNT(*) AS active_standardized_fact_count, "
        "SUM(CASE WHEN COALESCE(graph_ready, 0) = 1 THEN 1 ELSE 0 END) "
        "AS active_graph_ready_fact_count, "
        "COUNT(DISTINCT entity_id) AS active_fact_entity_count, "
        "COUNT(DISTINCT metric_id) AS active_fact_metric_count, "
        "MIN(period_end) AS active_fact_min_date, "
        "MAX(period_end) AS active_fact_max_date "
        "FROM standardized_facts WHERE COALESCE(is_active, 1) = 1 "
        "GROUP BY source_id"
    )
    return {
        str(row["source_id"]): dict(row)
        for row in rows
        if row["source_id"]
    }


def _base_source_report(
    source_id: str,
    registry: dict[str, Any],
    objects: list[dict[str, Any]],
    records: list[dict[str, Any]],
    entities: list[dict[str, Any]],
    jobs: list[dict[str, Any]],
    active_fact_summary: dict[str, Any],
) -> dict[str, Any]:
    dates = []
    for obj in objects:
        dates.append(_parse_date(obj.get("source_publish_date")))
    for record in records:
        dates.append(_parse_date(record.get("period_hint")))

    record_type_counts = Counter(row.get("record_type") or "unknown" for row in records)
    object_type_counts = Counter(row.get("object_type") or "unknown" for row in objects)
    validation_counts = Counter(row.get("validation_status") or "unknown" for row in objects)
    response_status_counts = Counter(str(row.get("response_status")) for row in objects)
    entity_hints = {row.get("entity_hint") for row in records if row.get("entity_hint")}
    metric_hints = {row.get("metric_hint") for row in records if row.get("metric_hint")}

    return {
        "source_id": source_id,
        "source_name": registry.get("source_name") or source_id,
        "provider": registry.get("provider"),
        "market": registry.get("market"),
        "authority_level": registry.get("authority_level"),
        "access_method": registry.get("access_method"),
        "update_frequency": registry.get("update_frequency"),
        "data_types": SOURCE_DATA_TYPES.get(source_id, []),
        "entity_types": SOURCE_ENTITY_TYPES.get(source_id, []),
        "object_count": len(objects),
        "record_count": len(records),
        "object_type_counts": dict(sorted(object_type_counts.items())),
        "record_type_counts": dict(sorted(record_type_counts.items())),
        "validation_status_counts": dict(sorted(validation_counts.items())),
        "response_status_counts": dict(sorted(response_status_counts.items())),
        "failed_object_count": sum(1 for row in objects if row.get("validation_status") == "failed"),
        "warning_object_count": sum(1 for row in objects if row.get("validation_status") == "warning"),
        "entity_count": len(entity_hints) or len(entities),
        "metric_count": len(metric_hints),
        "source_entity_count": len(entities),
        "min_date": _min_date(dates),
        "max_date": _max_date(dates),
        "time_granularity": [],
        "missing_rate": 0.0 if objects else 1.0,
        "missing_items": [],
        "coverage_notes": [],
        "active_standardized_fact_count": int(
            active_fact_summary.get("active_standardized_fact_count") or 0
        ),
        "active_graph_ready_fact_count": int(
            active_fact_summary.get("active_graph_ready_fact_count") or 0
        ),
        "active_fact_entity_count": int(
            active_fact_summary.get("active_fact_entity_count") or 0
        ),
        "active_fact_metric_count": int(
            active_fact_summary.get("active_fact_metric_count") or 0
        ),
        "active_fact_min_date": active_fact_summary.get("active_fact_min_date"),
        "active_fact_max_date": active_fact_summary.get("active_fact_max_date"),
        "parse_ready": bool(
            PARSE_READY.get(source_id, False)
            or active_fact_summary.get("active_standardized_fact_count")
        ),
        "quality_level": "unclassified",
        "latest_job_status": jobs[-1].get("status") if jobs else None,
    }


def _audit_sec_companyfacts(report: dict[str, Any] | None, config: dict[str, Any]) -> None:
    if not report:
        return
    companies = config.get("sec", {}).get("sample_companies", [])
    target_tickers = {company.get("ticker") or str(company.get("cik")).zfill(10) for company in companies}
    records = _records_for_source("sec_companyfacts")
    observed_tickers = set()
    concepts = set()
    dates = []
    future_date_count = 0
    today = date.today()
    for record in records:
        observed_tickers.add(record.get("entity_hint"))
        payload = _json_value(record.get("record_json"))
        facts = payload.get("facts", {}) if isinstance(payload, dict) else {}
        for namespace, namespace_facts in facts.items():
            if not isinstance(namespace_facts, dict):
                continue
            for concept, concept_payload in namespace_facts.items():
                concepts.add(f"{namespace}:{concept}")
                units = concept_payload.get("units", {}) if isinstance(concept_payload, dict) else {}
                for unit_items in units.values():
                    if not isinstance(unit_items, list):
                        continue
                    for item in unit_items:
                        if isinstance(item, dict):
                            parsed = _parse_date(item.get("end") or item.get("filed"))
                            if parsed and parsed <= today:
                                dates.append(parsed)
                            elif parsed:
                                future_date_count += 1
    missing = sorted(target_tickers - observed_tickers)
    report["entity_count"] = len(observed_tickers)
    report["metric_count"] = len(concepts)
    _merge_dates(report, dates)
    report["time_granularity"] = ["fiscal_period", "annual", "quarterly"]
    report["missing_rate"] = _rate(len(missing), len(target_tickers))
    report["missing_items"] = [{"type": "missing_companyfacts_company", "ticker": item} for item in missing[:100]]
    report["coverage_notes"].append("XBRL companyfacts JSON is available as raw records; facts are not normalized yet.")
    if future_date_count:
        report["coverage_notes"].append(f"Ignored {future_date_count} SEC companyfacts dates later than the audit date when computing max_date.")
    _set_quality(report)


def _audit_sec_submissions(report: dict[str, Any] | None, config: dict[str, Any]) -> None:
    if not report:
        return
    companies = config.get("sec", {}).get("sample_companies", [])
    target_tickers = {company.get("ticker") or str(company.get("cik")).zfill(10) for company in companies}
    records = _records_for_source("sec_submissions")
    observed_tickers = set()
    forms = set()
    dates = []
    for record in records:
        observed_tickers.add(record.get("entity_hint"))
        payload = _json_value(record.get("record_json"))
        recent = payload.get("filings", {}).get("recent", {}) if isinstance(payload, dict) else {}
        for form in recent.get("form", []) if isinstance(recent, dict) else []:
            if form:
                forms.add(form)
        for filing_date in recent.get("filingDate", []) if isinstance(recent, dict) else []:
            dates.append(_parse_date(filing_date))
    missing = sorted(target_tickers - observed_tickers)
    report["entity_count"] = len(observed_tickers)
    report["metric_count"] = len(forms)
    _merge_dates(report, dates)
    report["time_granularity"] = ["event_date", "filing_date"]
    report["missing_rate"] = _rate(len(missing), len(target_tickers))
    report["missing_items"] = [{"type": "missing_submissions_company", "ticker": item} for item in missing[:100]]
    _set_quality(report)


def _audit_sec_filings(report: dict[str, Any] | None, config: dict[str, Any]) -> None:
    if not report:
        return
    sec_cfg = config.get("sec", {})
    companies = sec_cfg.get("filing_companies") or sec_cfg.get("sample_companies", [])
    target_tickers = {company.get("ticker") or str(company.get("cik")).zfill(10) for company in companies}
    expected_forms = set(sec_cfg.get("filing_forms", ["10-K", "10-Q", "8-K"]))
    limit_per_company = int(sec_cfg.get("filing_limit_per_company", 0) or 0)
    limits_by_form = {
        str(form): max(int(limit), 0)
        for form, limit in dict(sec_cfg.get("filing_limits_by_form") or {}).items()
        if str(form) in expected_forms
    }
    records = _records_for_source("sec_filings")
    by_ticker_forms: dict[str, set[str]] = defaultdict(set)
    by_ticker_form_counts: dict[str, Counter[str]] = defaultdict(Counter)
    dates = []
    forms = set()
    for record in records:
        ticker = record.get("entity_hint")
        form = record.get("metric_hint")
        if ticker and form:
            by_ticker_forms[ticker].add(form)
            by_ticker_form_counts[ticker][form] += 1
            forms.add(form)
        dates.append(_parse_date(record.get("period_hint")))
    missing_10k = sorted(ticker for ticker in target_tickers if "10-K" in expected_forms and "10-K" not in by_ticker_forms.get(ticker, set()))
    expected_per_company = (
        sum(limits_by_form.values()) if limits_by_form else limit_per_company
    )
    expected_docs = (
        len(target_tickers) * expected_per_company
        if expected_per_company
        else len(records)
    )
    if limits_by_form:
        missing_docs = sum(
            max(limit - by_ticker_form_counts[ticker].get(form, 0), 0)
            for ticker in target_tickers
            for form, limit in limits_by_form.items()
        )
    else:
        missing_docs = max(expected_docs - len(records), 0)
    report["entity_count"] = len(by_ticker_forms)
    report["metric_count"] = len(forms)
    _merge_dates(report, dates)
    report["time_granularity"] = ["filing_date", "report_date"]
    report["missing_rate"] = _rate(missing_docs, expected_docs)
    report["missing_items"] = [{"type": "company_without_downloaded_10K", "ticker": item} for item in missing_10k[:100]]
    if missing_10k:
        report["coverage_notes"].append(f"{len(missing_10k)} configured companies do not have a downloaded 10-K in the current filing sample.")
    if limits_by_form:
        report["coverage_notes"].append(
            "SEC filing coverage uses per-form targets: "
            + ", ".join(
                f"{form}={limit}" for form, limit in sorted(limits_by_form.items())
            )
            + "."
        )
    report["coverage_notes"].append("Filing documents are raw HTML/TXT/PDF-like source documents and are not parse-ready for facts.")
    _set_quality(report)


def _audit_fred(report: dict[str, Any] | None, config: dict[str, Any]) -> None:
    if not report:
        return
    target_series = set(config.get("fred", {}).get("series_ids", []))
    records = _records_for_source("fred_observations")
    observation_series = set()
    series_with_values: dict[str, int] = defaultdict(int)
    frequencies = Counter()
    dates = []
    for record in records:
        record_type = record.get("record_type")
        series_id = record.get("entity_hint")
        payload = _json_value(record.get("record_json"))
        if record_type == "fred_observation":
            if series_id:
                observation_series.add(series_id)
            if isinstance(payload, dict) and payload.get("value") not in {None, "."}:
                series_with_values[series_id] += 1
            dates.append(_parse_date(record.get("period_hint")))
        elif record_type == "fred_series_metadata" and isinstance(payload, dict):
            freq = payload.get("frequency_short") or payload.get("frequency")
            if freq:
                frequencies[str(freq)] += 1
    missing = sorted(target_series - observation_series)
    zero_value_series = sorted(series for series in target_series if series_with_values.get(series, 0) == 0)
    report["entity_count"] = len(observation_series)
    report["metric_count"] = len(target_series or observation_series)
    _merge_dates(report, dates)
    report["time_granularity"] = sorted(frequencies) or ["mixed"]
    report["frequency_counts"] = dict(sorted(frequencies.items()))
    report["missing_rate"] = _rate(len(missing), len(target_series))
    report["missing_items"] = [{"type": "missing_fred_series", "series_id": item} for item in missing]
    report["missing_items"].extend({"type": "fred_series_without_non_null_values", "series_id": item} for item in zero_value_series[:100])
    _set_quality(report)


def _audit_worldbank(report: dict[str, Any] | None, config: dict[str, Any]) -> None:
    if not report:
        return
    wb_cfg = config.get("worldbank", {})
    countries = list(wb_cfg.get("countries", []))
    indicators = list(wb_cfg.get("indicators", []))
    years = _year_range(wb_cfg.get("date_range"))
    records = _records_for_source("worldbank_indicators")
    observed_countries = set()
    observed_indicators = set()
    observed_values: dict[tuple[str, str], set[int]] = defaultdict(set)
    null_values: list[dict[str, Any]] = []
    dates = []
    for record in records:
        payload = _json_value(record.get("record_json"))
        if record.get("record_type") == "wb_observation":
            country = record.get("entity_hint")
            indicator = record.get("metric_hint")
            year = _year_from_value(record.get("period_hint"))
            if country:
                observed_countries.add(country)
            if indicator:
                observed_indicators.add(indicator)
            if year is not None:
                dates.append(date(year, 1, 1))
            value = payload.get("value") if isinstance(payload, dict) else None
            if country and indicator and year is not None and value is not None:
                observed_values[(country, indicator)].add(year)
            elif country and indicator and year is not None:
                null_values.append({"country": country, "indicator": indicator, "year": year})
    missing_years = []
    for country in countries:
        for indicator in indicators:
            have = observed_values.get((country, indicator), set())
            for year in years:
                if year not in have:
                    missing_years.append({"country": country, "indicator": indicator, "year": year})
    expected_cells = len(countries) * len(indicators) * len(years)
    report["entity_count"] = len(observed_countries)
    report["metric_count"] = len(observed_indicators)
    _merge_dates(report, dates)
    report["time_granularity"] = ["annual"]
    report["expected_observation_cells"] = expected_cells
    report["observed_non_null_observation_cells"] = max(expected_cells - len(missing_years), 0) if expected_cells else sum(len(v) for v in observed_values.values())
    report["null_observation_cells"] = len(null_values)
    report["missing_rate"] = _rate(len(missing_years), expected_cells)
    report["missing_items"] = [{"type": "missing_or_null_worldbank_observation", **item} for item in missing_years[:500]]
    if len(missing_years) > 500:
        report["coverage_notes"].append(f"Missing/null World Bank cells truncated in JSON: {len(missing_years)} total.")
    _set_quality(report)


def _audit_imf(report: dict[str, Any] | None, config: dict[str, Any]) -> None:
    if not report:
        return
    targets = config.get("imf", {}).get("targets", [])
    records = _records_for_source("imf_sdmx")
    observed_targets = {record.get("metric_hint") for record in records if record.get("metric_hint")}
    target_names = {target.get("name") for target in targets if target.get("name")}
    missing = sorted(target_names - observed_targets)
    report["entity_count"] = 0
    report["metric_count"] = len(observed_targets or target_names)
    report["time_granularity"] = ["mixed_or_unknown"]
    report["missing_rate"] = _rate(len(missing), len(target_names))
    report["missing_items"] = [{"type": "missing_imf_target", "target": item} for item in missing]
    report["coverage_notes"].append("IMF raw JSON objects are downloaded, but observation-level raw_records are not expanded yet.")
    _set_quality(report)


def _audit_cninfo(report: dict[str, Any] | None, config: dict[str, Any]) -> None:
    if not report:
        return
    generated_targets = config.get("cninfo", {}).get("announcements", [])
    records = _records_for_source("cninfo_announcements")
    seen_urls = set()
    companies = set()
    report_types = set()
    dates = []
    stock_year_type: dict[str, set[str]] = defaultdict(set)
    for record in records:
        payload = _json_value(record.get("record_json"))
        if isinstance(payload, dict):
            url = payload.get("url")
            stock = payload.get("stock_code") or record.get("entity_hint")
            year = payload.get("year") or record.get("period_hint")
            report_type = payload.get("report_type") or record.get("metric_hint")
            if url:
                seen_urls.add(url)
            if stock:
                companies.add(stock)
            if report_type:
                report_types.add(report_type)
            if stock and year and report_type:
                stock_year_type[f"{stock}:{year}"].add(report_type)
            source_row = payload.get("source_row") or {}
            millis = source_row.get("announcementTime") if isinstance(source_row, dict) else None
            if isinstance(millis, int):
                dates.append(_date_from_epoch_ms(millis))
        dates.append(_parse_date(record.get("period_hint")))
    target_urls = {item.get("url") for item in generated_targets if item.get("url")}
    missing = sorted(target_urls - seen_urls)
    report["entity_count"] = len(companies)
    report["metric_count"] = len(report_types)
    _merge_dates(report, dates)
    report["time_granularity"] = ["announcement_date", "report_year"]
    report["stock_year_report_types"] = {key: sorted(value) for key, value in sorted(stock_year_type.items())}
    report["missing_rate"] = _rate(len(missing), len(target_urls)) if target_urls else report["missing_rate"]
    report["missing_items"] = [{"type": "missing_cninfo_pdf", "url": item} for item in missing]
    if report.get("active_standardized_fact_count"):
        report["coverage_notes"].append(
            "CNInfo PDF parsing has produced "
            f"{report['active_standardized_fact_count']} active standardized facts; "
            "document-level completeness is evaluated by the Greater China quality gate."
        )
    else:
        report["coverage_notes"].append(
            "CNInfo PDFs are present, but no active standardized facts were found."
        )
    _set_quality(report)


def _audit_exchange_announcements(report: dict[str, Any] | None) -> None:
    if not report:
        return
    report["missing_rate"] = 1.0
    report["missing_items"] = [{"type": "source_not_ingested", "source": "exchange_announcements"}]
    report["coverage_notes"].append("Dedicated exchange announcement connectors have not been ingested yet; CNInfo is present separately.")
    _set_quality(report)


_CURRENT_RECORDS: dict[str, list[dict[str, Any]]] = {}


def _records_for_source(source_id: str) -> list[dict[str, Any]]:
    return _CURRENT_RECORDS.get(source_id, [])


def _group_by(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row.get(key)].append(row)
    if key == "source_id" and rows and "record_json" in rows[0]:
        global _CURRENT_RECORDS
        _CURRENT_RECORDS = grouped
    return grouped


def _summary_row(report: dict[str, Any]) -> dict[str, Any]:
    return {column: report.get(column) for column in SUMMARY_COLUMNS}


def _set_quality(report: dict[str, Any]) -> None:
    if report["object_count"] == 0:
        report["quality_level"] = "not_ingested"
    elif report["failed_object_count"] > 0:
        report["quality_level"] = "problem"
    elif report["parse_ready"] and report["missing_rate"] <= 0.05:
        report["quality_level"] = "ready_high"
    elif report["parse_ready"]:
        report["quality_level"] = "ready_partial"
    elif report["missing_rate"] <= 0.05:
        report["quality_level"] = "raw_only_high"
    else:
        report["quality_level"] = "raw_only_partial"


def _data_sources(source_reports: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for report in source_reports.values():
        rows.append({
            "source_id": report["source_id"],
            "provider": report.get("provider"),
            "market": report.get("market"),
            "object_count": report.get("object_count"),
            "parse_ready": report.get("parse_ready"),
            "active_standardized_fact_count": report.get(
                "active_standardized_fact_count"
            ),
            "active_graph_ready_fact_count": report.get(
                "active_graph_ready_fact_count"
            ),
            "quality_level": report.get("quality_level"),
        })
    return sorted(rows, key=lambda row: row["source_id"])


def _entity_inventory(source_reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    inventory: dict[str, Any] = defaultdict(list)
    for report in source_reports.values():
        for entity_type in report.get("entity_types", []):
            inventory[entity_type].append({"source_id": report["source_id"], "entity_count": report.get("entity_count")})
    return dict(sorted(inventory.items()))


def _data_type_inventory(source_reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    inventory: dict[str, Any] = defaultdict(list)
    for report in source_reports.values():
        for data_type in report.get("data_types", []):
            inventory[data_type].append({"source_id": report["source_id"], "object_count": report.get("object_count")})
    return dict(sorted(inventory.items()))


def _json_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if value is None:
        return None
    text = str(value)
    if not text:
        return None
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", text)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            return None
    match = re.match(r"^(\d{4})$", text)
    if match:
        return date(int(match.group(1)), 1, 1)
    return None


def _date_from_epoch_ms(value: int) -> date | None:
    try:
        from datetime import datetime, timezone

        return datetime.fromtimestamp(value / 1000, tz=timezone.utc).date()
    except Exception:
        return None


def _year_from_value(value: Any) -> int | None:
    parsed = _parse_date(value)
    if parsed:
        return parsed.year
    return None


def _year_range(value: Any) -> list[int]:
    if not value:
        return []
    text = str(value)
    if ":" in text:
        start, end = text.split(":", 1)
        if start.isdigit() and end.isdigit():
            return list(range(int(start), int(end) + 1))
    if text.isdigit():
        return [int(text)]
    return []


def _min_date(values: list[date | None]) -> str | None:
    dates = [value for value in values if value]
    return min(dates).isoformat() if dates else None


def _max_date(values: list[date | None]) -> str | None:
    dates = [value for value in values if value]
    return max(dates).isoformat() if dates else None


def _merge_dates(report: dict[str, Any], values: list[date | None]) -> None:
    dates = [value for value in values if value]
    if not dates:
        return
    existing_min = _parse_date(report.get("min_date"))
    existing_max = _parse_date(report.get("max_date"))
    if existing_min:
        dates.append(existing_min)
    if existing_max:
        dates.append(existing_max)
    report["min_date"] = min(dates).isoformat()
    report["max_date"] = max(dates).isoformat()


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 6)


def _markdown_report(report: dict[str, Any]) -> str:
    lines = ["# Data Coverage Report", "", f"Generated: {report['report_generated_at']}", ""]
    lines.append("## Summary")
    lines.append("")
    lines.append("| source_id | entities | metrics | min_date | max_date | objects | missing_rate | parse_ready | quality |")
    lines.append("|---|---:|---:|---|---|---:|---:|---|---|")
    for row in report["data_coverage_report"]:
        lines.append(
            "| {source_id} | {entity_count} | {metric_count} | {min_date} | {max_date} | {object_count} | {missing_rate:.4f} | {parse_ready} | {quality_level} |".format(
                source_id=row.get("source_id"),
                entity_count=row.get("entity_count") or 0,
                metric_count=row.get("metric_count") or 0,
                min_date=row.get("min_date") or "",
                max_date=row.get("max_date") or "",
                object_count=row.get("object_count") or 0,
                missing_rate=float(row.get("missing_rate") or 0),
                parse_ready=row.get("parse_ready"),
                quality_level=row.get("quality_level"),
            )
        )
    lines.append("")
    lines.append("## Missing Data Highlights")
    lines.append("")
    for source in report["source_reports"]:
        missing = source.get("missing_items", [])
        if not missing:
            continue
        lines.append(f"### {source['source_id']}")
        for item in missing[:20]:
            lines.append(f"- `{json.dumps(item, ensure_ascii=False, sort_keys=True)}`")
        if len(missing) > 20:
            lines.append(f"- ... {len(missing) - 20} more in JSON report")
        lines.append("")
    lines.append("## Recommended Build Order")
    lines.append("")
    for source_id in report["recommended_build_order"]:
        lines.append(f"- {source_id}")
    lines.append("")
    return "\n".join(lines)
