from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from finraw.builds import deactivate_active_rows, finish_build, start_build
from finraw.db.client import DBProtocol


COMPANY_SOURCE_IDS = {
    "sec_companyfacts",
    "sec_submissions",
    "sec_filings",
    "cninfo_announcements",
    "bse_disclosures",
    "hkex_disclosures",
}

CN_COMPANY_SOURCES = {
    "cninfo_announcements": ("cninfo", "cninfo_pdf_announcement"),
    "bse_disclosures": ("bse", "bse_pdf_announcement"),
    "hkex_disclosures": ("hkex", "hkex_pdf_annual_report"),
}

FRED_CURRENCY_PAIRS = {
    "DEXUSEU": {"entity_id": "EUR_USD", "canonical_name": "Euro to U.S. Dollar Spot Exchange Rate", "currency": "EUR/USD"},
    "DEXJPUS": {"entity_id": "USD_JPY", "canonical_name": "U.S. Dollar to Japanese Yen Spot Exchange Rate", "currency": "USD/JPY"},
    "DEXCHUS": {"entity_id": "USD_CNY", "canonical_name": "U.S. Dollar to Chinese Yuan Renminbi Spot Exchange Rate", "currency": "USD/CNY"},
}

FRED_INDEX_SERIES = {
    "DTWEXBGS": {"entity_id": "USD_BROAD_INDEX", "canonical_name": "Nominal Broad U.S. Dollar Index"},
}

CURATED_ENTITY_ALIASES = {
    "AAPL_US": ["苹果公司"],
}


def refresh_entity_normalization(db: DBProtocol, config: dict[str, Any], output_dir: str | None = None) -> dict[str, Any]:
    build_id = start_build(db, layer="fact_build", command="refresh-entities", prefix="entity_normalization")
    entities, aliases, securities, relationships, series_maps, diagnostics = build_entity_normalization(db, config)
    for table in ["source_series_entity_map", "entity_relationships", "canonical_securities", "entity_alias_map", "canonical_entities"]:
        deactivate_active_rows(db, table, build_id)
    for entity in entities:
        db.execute(
            """
            INSERT INTO canonical_entities (
                entity_id, canonical_name, entity_type, market, country, exchange,
                ticker, cik, isin, currency, fiscal_year_end, industry, build_id, is_active, superseded_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (entity_id) DO UPDATE SET
                canonical_name=excluded.canonical_name,
                entity_type=excluded.entity_type,
                market=excluded.market,
                country=excluded.country,
                exchange=excluded.exchange,
                ticker=excluded.ticker,
                cik=excluded.cik,
                isin=excluded.isin,
                currency=excluded.currency,
                fiscal_year_end=excluded.fiscal_year_end,
                industry=excluded.industry,
                build_id=excluded.build_id,
                is_active=1,
                superseded_by=NULL,
                updated_at=CURRENT_TIMESTAMP
            """,
            [
                entity.get("entity_id"),
                entity.get("canonical_name"),
                entity.get("entity_type"),
                entity.get("market"),
                entity.get("country"),
                entity.get("exchange"),
                entity.get("ticker"),
                entity.get("cik"),
                entity.get("isin"),
                entity.get("currency"),
                entity.get("fiscal_year_end"),
                entity.get("industry"),
                build_id,
                1,
                None,
            ],
        )
    for security in securities:
        db.execute(
            """
            INSERT INTO canonical_securities (
                security_id, company_entity_id, canonical_name, security_type, market, country, exchange,
                ticker, composite_ticker, figi, isin, cusip, currency, is_primary_listing, listing_status,
                valid_from, valid_to, build_id, is_active, superseded_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (security_id) DO UPDATE SET
                company_entity_id=excluded.company_entity_id,
                canonical_name=excluded.canonical_name,
                security_type=excluded.security_type,
                market=excluded.market,
                country=excluded.country,
                exchange=excluded.exchange,
                ticker=excluded.ticker,
                composite_ticker=excluded.composite_ticker,
                figi=excluded.figi,
                isin=excluded.isin,
                cusip=excluded.cusip,
                currency=excluded.currency,
                is_primary_listing=excluded.is_primary_listing,
                listing_status=excluded.listing_status,
                valid_from=excluded.valid_from,
                valid_to=excluded.valid_to,
                build_id=excluded.build_id,
                is_active=1,
                superseded_by=NULL,
                updated_at=CURRENT_TIMESTAMP
            """,
            [
                security.get("security_id"),
                security.get("company_entity_id"),
                security.get("canonical_name"),
                security.get("security_type"),
                security.get("market"),
                security.get("country"),
                security.get("exchange"),
                security.get("ticker"),
                security.get("composite_ticker"),
                security.get("figi"),
                security.get("isin"),
                security.get("cusip"),
                security.get("currency"),
                security.get("is_primary_listing", 1),
                security.get("listing_status"),
                security.get("valid_from"),
                security.get("valid_to"),
                build_id,
                1,
                None,
            ],
        )
    for relationship in relationships:
        db.execute(
            """
            INSERT INTO entity_relationships (
                relationship_id, subject_entity_id, relationship_type, object_id, object_type, object_entity_id,
                source_id, source_code, confidence_score, valid_from, valid_to, notes, build_id, is_active, superseded_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (relationship_id) DO UPDATE SET
                subject_entity_id=excluded.subject_entity_id,
                relationship_type=excluded.relationship_type,
                object_id=excluded.object_id,
                object_type=excluded.object_type,
                object_entity_id=excluded.object_entity_id,
                source_id=excluded.source_id,
                source_code=excluded.source_code,
                confidence_score=excluded.confidence_score,
                valid_from=excluded.valid_from,
                valid_to=excluded.valid_to,
                notes=excluded.notes,
                build_id=excluded.build_id,
                is_active=1,
                superseded_by=NULL
            """,
            [
                relationship.get("relationship_id"),
                relationship.get("subject_entity_id"),
                relationship.get("relationship_type"),
                relationship.get("object_id"),
                relationship.get("object_type"),
                relationship.get("object_entity_id"),
                relationship.get("source_id"),
                relationship.get("source_code"),
                relationship.get("confidence_score"),
                relationship.get("valid_from"),
                relationship.get("valid_to"),
                _json_text(relationship.get("notes")),
                build_id,
                1,
                None,
            ],
        )
    for series_map in series_maps:
        db.execute(
            """
            INSERT INTO source_series_entity_map (
                series_map_id, source_id, series_id, series_entity_id, metric_id, applies_to_entity_id,
                instrument_entity_id, frequency, source_units, seasonal_adjustment, notes, build_id, is_active, superseded_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (series_map_id) DO UPDATE SET
                source_id=excluded.source_id,
                series_id=excluded.series_id,
                series_entity_id=excluded.series_entity_id,
                metric_id=excluded.metric_id,
                applies_to_entity_id=excluded.applies_to_entity_id,
                instrument_entity_id=excluded.instrument_entity_id,
                frequency=excluded.frequency,
                source_units=excluded.source_units,
                seasonal_adjustment=excluded.seasonal_adjustment,
                notes=excluded.notes,
                build_id=excluded.build_id,
                is_active=1,
                superseded_by=NULL
            """,
            [
                series_map.get("series_map_id"),
                series_map.get("source_id"),
                series_map.get("series_id"),
                series_map.get("series_entity_id"),
                series_map.get("metric_id"),
                series_map.get("applies_to_entity_id"),
                series_map.get("instrument_entity_id"),
                series_map.get("frequency"),
                series_map.get("source_units"),
                series_map.get("seasonal_adjustment"),
                _json_text(series_map.get("notes")),
                build_id,
                1,
                None,
            ],
        )

    for alias in aliases:
        db.execute(
            """
            INSERT INTO entity_alias_map (
                alias_id, entity_id, source_id, source_code, source_name, alias, confidence_score, build_id, is_active, superseded_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (alias_id) DO UPDATE SET
                entity_id=excluded.entity_id,
                source_id=excluded.source_id,
                source_code=excluded.source_code,
                source_name=excluded.source_name,
                alias=excluded.alias,
                confidence_score=excluded.confidence_score,
                build_id=excluded.build_id,
                is_active=1,
                superseded_by=NULL
            """,
            [
                alias.get("alias_id"),
                alias.get("entity_id"),
                alias.get("source_id"),
                alias.get("source_code"),
                alias.get("source_name"),
                alias.get("alias"),
                alias.get("confidence_score"),
                build_id,
                1,
                None,
            ],
        )
    report = {
        "build_id": build_id,
        "canonical_entity_count": len(entities),
        "alias_count": len(aliases),
        "security_count": len(securities),
        "relationship_count": len(relationships),
        "source_series_map_count": len(series_maps),
        "entity_type_counts": dict(sorted(Counter(entity["entity_type"] for entity in entities).items())),
        "market_counts": dict(sorted(Counter(entity.get("market") or "unknown" for entity in entities).items())),
        "diagnostics": diagnostics,
        "sample_entities": entities[:20],
        "sample_aliases": aliases[:30],
        "sample_securities": securities[:20],
        "sample_series_maps": series_maps[:20],
    }
    if output_dir:
        paths = write_entity_normalization_report(report, output_dir)
        report["written_files"] = [str(path) for path in paths]
    finish_build(db, build_id, "success", f"canonical_entity_count={len(entities)}; alias_count={len(aliases)}; security_count={len(securities)}; source_series_map_count={len(series_maps)}")
    return report


def build_entity_normalization(db: DBProtocol, config: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    source_entities = [dict(row) for row in db.fetchall("SELECT * FROM source_entities")]
    raw_records = [dict(row) for row in db.fetchall("SELECT source_id, record_type, record_key, record_json, entity_hint, metric_hint FROM raw_records")]
    fred_metric_by_series = _load_fred_metric_map(db)

    entity_by_id: dict[str, dict[str, Any]] = {}
    alias_by_id: dict[str, dict[str, Any]] = {}
    securities: dict[str, dict[str, Any]] = {}
    relationships: dict[str, dict[str, Any]] = {}
    series_maps: dict[str, dict[str, Any]] = {}
    diagnostics: dict[str, Any] = {
        "unmapped_source_entities": [],
        "skipped_records": [],
        "notes": [],
    }

    _add_sec_companies(entity_by_id, alias_by_id, source_entities, raw_records, config)
    _add_cninfo_companies(entity_by_id, alias_by_id, source_entities, raw_records, config)
    _add_worldbank_countries(entity_by_id, alias_by_id, source_entities)
    _add_imf_countries(entity_by_id, alias_by_id, raw_records)
    _add_fred_entities(entity_by_id, alias_by_id, source_entities, fred_metric_by_series, series_maps, relationships)
    _add_company_security_mdm(entity_by_id, securities, relationships)
    _add_diagnostics(diagnostics, source_entities, entity_by_id)

    entities = sorted(entity_by_id.values(), key=lambda row: (row["entity_type"], row["entity_id"]))
    aliases = sorted(alias_by_id.values(), key=lambda row: (row["entity_id"], row.get("source_id") or "", row.get("alias") or ""))
    security_rows = sorted(securities.values(), key=lambda row: row["security_id"])
    relationship_rows = sorted(relationships.values(), key=lambda row: row["relationship_id"])
    series_map_rows = sorted(series_maps.values(), key=lambda row: row["series_map_id"])
    return entities, aliases, security_rows, relationship_rows, series_map_rows, diagnostics


def write_entity_normalization_report(report: dict[str, Any], output_dir: str) -> list[Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "entity_normalization_report.json"
    md_path = out / "entity_normalization_report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    md_path.write_text(_markdown_report(report), encoding="utf-8")
    return [json_path, md_path]


def _add_sec_companies(
    entity_by_id: dict[str, dict[str, Any]],
    alias_by_id: dict[str, dict[str, Any]],
    source_entities: list[dict[str, Any]],
    raw_records: list[dict[str, Any]],
    config: dict[str, Any],
) -> None:
    companies = []
    seen_ciks = set()
    submission_by_cik: dict[str, dict[str, Any]] = {}
    for record in raw_records:
        if record.get("record_type") != "sec_submissions_json":
            continue
        payload = _json_value(record.get("record_json"))
        if not isinstance(payload, dict):
            continue
        cik = _cik10(payload.get("cik"))
        if cik:
            submission_by_cik[cik] = payload

    for company in config.get("sec", {}).get("sample_companies", []):
        cik = _cik10(company.get("cik"))
        submission = submission_by_cik.get(cik or "", {})
        if cik:
            seen_ciks.add(cik)
        companies.append({
            "ticker": _upper(company.get("ticker")),
            "cik": cik,
            "name": company.get("name") or company.get("ticker"),
            "exchange": company.get("exchange"),
            "industry": company.get("industry") or submission.get("sicDescription"),
            "source": "config+sec_submissions" if submission else "config",
        })

    for record in raw_records:
        if record.get("record_type") != "sec_submissions_json":
            continue
        payload = _json_value(record.get("record_json"))
        if not isinstance(payload, dict):
            continue
        cik = _cik10(payload.get("cik"))
        if cik in seen_ciks:
            continue
        ticker = _upper(record.get("entity_hint"))
        companies.append({
            "ticker": ticker,
            "cik": cik,
            "name": payload.get("name") or ticker or cik,
            "exchange": None,
            "industry": payload.get("sicDescription"),
            "source": "sec_submissions",
        })
        if cik:
            seen_ciks.add(cik)

    for company in companies:
        ticker = company.get("ticker")
        cik = company.get("cik")
        if not ticker and not cik:
            continue
        entity_id = f"{ticker}_US" if ticker else f"CIK{cik}_US"
        _upsert_entity(entity_by_id, {
            "entity_id": entity_id,
            "canonical_name": company.get("name") or ticker or f"CIK{cik}",
            "entity_type": "company",
            "market": "US",
            "country": "US",
            "exchange": company.get("exchange"),
            "ticker": ticker,
            "cik": cik,
            "isin": None,
            "currency": "USD",
            "fiscal_year_end": None,
            "industry": company.get("industry"),
        })
        short_name = _short_company_alias(company.get("name"))
        aliases = [ticker, company.get("name"), short_name, cik, f"CIK{cik}" if cik else None, f"CIK{int(cik)}" if cik else None]
        for curated_alias in CURATED_ENTITY_ALIASES.get(entity_id, []):
            _add_alias(alias_by_id, entity_id, None, None, "curated_entity_alias", curated_alias, 0.82)
        for source_id in ["sec_companyfacts", "sec_submissions", "sec_filings"]:
            source_code = cik if source_id != "sec_filings" else ticker or cik
            for alias in aliases:
                _add_alias(alias_by_id, entity_id, source_id, source_code, company.get("name"), alias, 0.98)


def _add_cninfo_companies(
    entity_by_id: dict[str, dict[str, Any]],
    alias_by_id: dict[str, dict[str, Any]],
    source_entities: list[dict[str, Any]],
    raw_records: list[dict[str, Any]],
    config: dict[str, Any],
) -> None:
    companies: dict[str, dict[str, Any]] = {}
    for source_id, (config_key, _) in CN_COMPANY_SOURCES.items():
        for item in config.get(config_key, {}).get("stock_pool", []):
            code = _clean_code(item.get("stock_code"))
            if not code:
                continue
            companies[code] = {
                "stock_code": code,
                "name": item.get("company_name") or code,
                "exchange": (
                    item.get("market")
                    or item.get("exchange")
                    or _cn_exchange_from_selector(item.get("selector"))
                    or ("BSE" if source_id == "bse_disclosures" else None)
                ),
                "industry": item.get("industry"),
                "source": "config",
                "source_ids": {source_id},
            }
    for source_entity in source_entities:
        source_id = str(source_entity.get("source_id") or "")
        if source_id not in CN_COMPANY_SOURCES:
            continue
        code = _clean_code(source_entity.get("source_code"))
        if not code:
            continue
        metadata = _json_value(source_entity.get("raw_metadata"))
        company = companies.setdefault(
            code,
            {
                "stock_code": code,
                "name": source_entity.get("source_name")
                or (metadata.get("secName") if isinstance(metadata, dict) else None)
                or code,
                "exchange": (
                    "BSE" if source_id == "bse_disclosures" else
                    "HKEX" if source_id == "hkex_disclosures" else
                    _cn_exchange_from_metadata(metadata)
                ),
                "industry": _cn_industry_from_metadata(metadata),
                "source": "source_entities",
                "source_ids": set(),
            },
        )
        company.setdefault("source_ids", set()).add(source_id)
    for record in raw_records:
        source_id = str(record.get("source_id") or "")
        source_spec = CN_COMPANY_SOURCES.get(source_id)
        if not source_spec or record.get("record_type") != source_spec[1]:
            continue
        payload = _json_value(record.get("record_json"))
        if not isinstance(payload, dict):
            continue
        code = _clean_code(payload.get("stock_code"))
        if not code:
            continue
        company = companies.setdefault(
            code,
            {
                "stock_code": code,
                "name": payload.get("company_name")
                or payload.get("source_row", {}).get("secName")
                or code,
                "exchange": (
                    "BSE" if source_id == "bse_disclosures" else
                    "HKEX" if source_id == "hkex_disclosures" else
                    _cn_exchange_from_metadata(payload.get("source_row"))
                ),
                "industry": _cn_industry_from_metadata(payload),
                "source": "raw_records",
                "source_ids": set(),
            },
        )
        company.setdefault("source_ids", set()).add(source_id)

    for company in companies.values():
        code = company["stock_code"]
        exchange = company.get("exchange") or "CN"
        source_ids = set(company.get("source_ids") or [])
        is_hk = "hkex_disclosures" in source_ids or exchange in {"HK", "HKEX"}
        exchange = "HKEX" if is_hk else exchange
        entity_id = f"{code}_{exchange}"
        _upsert_entity(entity_by_id, {
            "entity_id": entity_id,
            "canonical_name": company.get("name") or code,
            "entity_type": "company",
            "market": "HK" if is_hk else "CN",
            "country": "HK" if is_hk else "CN",
            "exchange": exchange,
            "ticker": code,
            "cik": None,
            "isin": None,
            "currency": "HKD" if is_hk else "CNY",
            "fiscal_year_end": None if is_hk else "12-31",
            "industry": company.get("industry"),
        })
        aliases = [code, company.get("name"), f"{code}.{exchange}" if exchange not in {"CN", None} else None]
        for source_id in sorted(company.get("source_ids") or []):
            for alias in aliases:
                _add_alias(
                    alias_by_id,
                    entity_id,
                    source_id,
                    code,
                    company.get("name"),
                    alias,
                    0.96,
                )


def _add_worldbank_countries(
    entity_by_id: dict[str, dict[str, Any]],
    alias_by_id: dict[str, dict[str, Any]],
    source_entities: list[dict[str, Any]],
) -> None:
    for source_entity in source_entities:
        if source_entity.get("source_id") != "worldbank_indicators":
            continue
        metadata = _json_value(source_entity.get("raw_metadata"))
        if not isinstance(metadata, dict) or metadata.get("kind") != "country":
            continue
        iso3 = _upper(source_entity.get("source_code"))
        if not iso3:
            continue
        entity_id = f"{iso3}_COUNTRY"
        region = metadata.get("region", {}) if isinstance(metadata.get("region"), dict) else {}
        country_name = source_entity.get("source_name") or metadata.get("name") or iso3
        _upsert_entity(entity_by_id, {
            "entity_id": entity_id,
            "canonical_name": country_name,
            "entity_type": "country",
            "market": "Global",
            "country": iso3,
            "exchange": None,
            "ticker": None,
            "cik": None,
            "isin": None,
            "currency": None,
            "fiscal_year_end": None,
            "industry": region.get("value"),
        })
        aliases = [iso3, metadata.get("id"), metadata.get("iso2Code"), country_name]
        for alias in aliases:
            _add_alias(alias_by_id, entity_id, "worldbank_indicators", iso3, country_name, alias, 0.97)


def _add_imf_countries(
    entity_by_id: dict[str, dict[str, Any]],
    alias_by_id: dict[str, dict[str, Any]],
    raw_records: list[dict[str, Any]],
) -> None:
    country_codes: set[str] = set()
    region_codes: set[str] = set()
    for record in raw_records:
        if record.get("record_type") != "imf_sdmx_response":
            continue
        payload = _json_value(record.get("record_json"))
        if not isinstance(payload, dict):
            continue
        storage_uri = payload.get("storage_uri")
        if not storage_uri:
            continue
        try:
            data = json.loads(Path(storage_uri).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        values = data.get("values") if isinstance(data, dict) else None
        if not isinstance(values, dict):
            continue
        for indicator_values in values.values():
            if not isinstance(indicator_values, dict):
                continue
            for code in indicator_values.keys():
                code = _upper(code)
                if not code:
                    continue
                if len(code) == 3 and code.isalpha():
                    country_codes.add(code)
                elif code.replace("_", "").isalnum():
                    region_codes.add(code)
    for iso3 in sorted(country_codes):
        entity_id = f"{iso3}_COUNTRY"
        existing = entity_by_id.get(entity_id)
        country_name = existing.get("canonical_name") if existing else _country_name(iso3)
        _upsert_entity(entity_by_id, {
            "entity_id": entity_id,
            "canonical_name": country_name,
            "entity_type": "country",
            "market": "Global",
            "country": iso3,
            "exchange": None,
            "ticker": None,
            "cik": None,
            "isin": None,
            "currency": None,
            "fiscal_year_end": None,
            "industry": existing.get("industry") if existing else None,
        })
        for alias in [iso3, country_name]:
            _add_alias(alias_by_id, entity_id, "imf_sdmx", iso3, country_name, alias, 0.9)

    for code in sorted(region_codes):
        entity_id = f"{code}_REGION"
        region_name = IMF_REGION_NAMES.get(code, code)
        _upsert_entity(entity_by_id, {
            "entity_id": entity_id,
            "canonical_name": region_name,
            "entity_type": "region",
            "market": "Global",
            "country": None,
            "exchange": None,
            "ticker": None,
            "cik": None,
            "isin": None,
            "currency": None,
            "fiscal_year_end": None,
            "industry": "IMF aggregate",
        })
        for alias in [code, region_name]:
            _add_alias(alias_by_id, entity_id, "imf_sdmx", code, region_name, alias, 0.86)


IMF_REGION_NAMES = {
    "ADVEC": "Advanced economies",
    "AS5": "ASEAN-5",
    "DA": "Emerging and developing Asia",
    "OEMDC": "Emerging market and developing economies",
    "EURO": "Euro area",
    "EU": "European Union",
    "WE": "World output group, advanced Europe",
    "MECA": "Middle East and Central Asia",
    "WEOWORLD": "World",
}


def _country_name(iso3: str) -> str:
    try:
        import pycountry
        country = pycountry.countries.get(alpha_3=iso3)
        if country:
            return country.name
    except Exception:
        pass
    return iso3


def _add_fred_entities(
    entity_by_id: dict[str, dict[str, Any]],
    alias_by_id: dict[str, dict[str, Any]],
    source_entities: list[dict[str, Any]],
    fred_metric_by_series: dict[str, str],
    series_maps: dict[str, dict[str, Any]],
    relationships: dict[str, dict[str, Any]],
) -> None:
    by_code = {
        source_entity.get("source_code"): source_entity
        for source_entity in source_entities
        if source_entity.get("source_id") == "fred_observations" and source_entity.get("source_code")
    }
    for code, source_entity in sorted(by_code.items()):
        metadata = _json_value(source_entity.get("raw_metadata"))
        metadata = metadata if isinstance(metadata, dict) else {}
        name = source_entity.get("source_name") or metadata.get("title") or code
        series_entity_id = f"FRED_SERIES_{_safe_token(code)}"
        _upsert_entity(entity_by_id, {
            "entity_id": series_entity_id,
            "canonical_name": name,
            "entity_type": "fred_series",
            "market": metadata.get("market") or _fred_market_hint(code, name),
            "country": "US" if _fred_default_us_series(code, name) else None,
            "exchange": None,
            "ticker": code,
            "cik": None,
            "isin": None,
            "currency": None,
            "fiscal_year_end": None,
            "industry": "FRED time series",
        })
        for alias in [code, name, metadata.get("id"), metadata.get("title")]:
            _add_alias(alias_by_id, series_entity_id, "fred_observations", code, name, alias, 0.99)

        target = _fred_target_spec(code, source_entity)
        target_id = target.get("entity_id")
        if target_id:
            _upsert_entity(entity_by_id, _fred_target_entity(target, code))
            for alias in target.get("aliases", []):
                _add_alias(alias_by_id, target_id, "fred_observations", code, name, alias, float(target.get("confidence_score", 0.86)))
            _add_relationship(relationships, series_entity_id, "series_applies_to", target_id, "canonical_entity", target_id, "fred_observations", code, float(target.get("confidence_score", 0.86)), {"series_title": name, "target_role": target.get("target_role")})

        metric_id = fred_metric_by_series.get(str(code))
        map_id = _series_map_id("fred_observations", str(code))
        target_role = target.get("target_role")
        series_maps[map_id] = {
            "series_map_id": map_id,
            "source_id": "fred_observations",
            "series_id": str(code),
            "series_entity_id": series_entity_id,
            "metric_id": metric_id,
            "applies_to_entity_id": target_id if target_role == "applies_to" else target.get("applies_to_entity_id"),
            "instrument_entity_id": target_id if target_role == "instrument" else target.get("instrument_entity_id"),
            "frequency": metadata.get("frequency") or metadata.get("frequency_short"),
            "source_units": metadata.get("units") or metadata.get("units_short"),
            "seasonal_adjustment": metadata.get("seasonal_adjustment") or metadata.get("seasonal_adjustment_short"),
            "notes": {
                "series_title": name,
                "target_role": target_role,
                "mapping_method": target.get("mapping_method"),
                "source_notes": metadata.get("notes"),
            },
        }


def _load_fred_metric_map(db: DBProtocol) -> dict[str, str]:
    try:
        rows = db.fetchall("SELECT raw_concept_name, metric_id FROM metric_alias_map WHERE source_id = ? AND COALESCE(is_active, 1) = 1", ["fred_observations"])
    except Exception:
        return {}
    out = {}
    for row in rows:
        item = dict(row)
        if item.get("raw_concept_name") and item.get("metric_id"):
            out[str(item["raw_concept_name"])] = str(item["metric_id"])
    return out


def _add_company_security_mdm(entity_by_id: dict[str, dict[str, Any]], securities: dict[str, dict[str, Any]], relationships: dict[str, dict[str, Any]]) -> None:
    for entity in entity_by_id.values():
        if entity.get("entity_type") != "company" or not entity.get("ticker"):
            continue
        exchange = entity.get("exchange") or entity.get("market")
        security_id = _security_id(entity.get("ticker"), exchange, "equity")
        composite = f"{entity.get('ticker')}.{exchange}" if exchange else entity.get("ticker")
        securities[security_id] = {
            "security_id": security_id,
            "company_entity_id": entity.get("entity_id"),
            "canonical_name": f"{entity.get('canonical_name')} Common Stock",
            "security_type": "equity",
            "market": entity.get("market"),
            "country": entity.get("country"),
            "exchange": exchange,
            "ticker": entity.get("ticker"),
            "composite_ticker": composite,
            "figi": None,
            "isin": entity.get("isin"),
            "cusip": None,
            "currency": entity.get("currency"),
            "is_primary_listing": 1,
            "listing_status": "active_or_latest_known",
            "valid_from": None,
            "valid_to": None,
        }
        _add_relationship(relationships, entity.get("entity_id"), "company_has_security", security_id, "security", None, None, entity.get("ticker"), 0.9, {"exchange": exchange, "composite_ticker": composite})


def _fred_target_spec(code: str, source_entity: dict[str, Any]) -> dict[str, Any]:
    code = str(code).upper()
    metadata = _json_value(source_entity.get("raw_metadata"))
    metadata = metadata if isinstance(metadata, dict) else {}
    title = str(source_entity.get("source_name") or metadata.get("title") or code)
    title_l = title.lower()
    if code in FRED_CURRENCY_PAIRS:
        spec = FRED_CURRENCY_PAIRS[code]
        return {**spec, "entity_type": "currency_pair", "target_role": "instrument", "market": "Global", "country": None, "exchange": None, "ticker": code, "confidence_score": 0.94, "mapping_method": "curated_fred_currency_pair", "aliases": [code, spec["canonical_name"], spec["currency"], spec["entity_id"].replace("_", "/")]}
    if code in FRED_INDEX_SERIES:
        spec = FRED_INDEX_SERIES[code]
        return {**spec, "entity_type": "index", "target_role": "instrument", "market": "US_Global", "country": "US", "exchange": None, "ticker": code, "currency": "USD", "confidence_score": 0.92, "mapping_method": "curated_fred_index", "aliases": [code, spec["canonical_name"]]}
    maturity = _treasury_maturity_label(code, title)
    if maturity:
        entity_id = f"US_TREASURY_{_safe_token(maturity)}_CMT"
        name = f"U.S. Treasury {maturity.replace('_', ' ')} Constant Maturity"
        return {"entity_id": entity_id, "canonical_name": name, "entity_type": "instrument", "target_role": "instrument", "market": "US Treasury", "country": "US", "exchange": None, "ticker": None, "currency": "USD", "confidence_score": 0.93, "mapping_method": "fred_treasury_constant_maturity_rule", "aliases": [code, title, name]}
    if code in {"FEDFUNDS", "EFFR"} or "federal funds" in title_l:
        return {"entity_id": "US_FED_FUNDS_MARKET", "canonical_name": "U.S. Federal Funds Market", "entity_type": "instrument", "target_role": "instrument", "market": "US Money Market", "country": "US", "exchange": None, "ticker": None, "currency": "USD", "confidence_score": 0.9, "mapping_method": "fred_money_market_rule", "aliases": [code, title, "Federal Funds Market"]}
    if code == "SOFR" or "secured overnight financing rate" in title_l:
        return {"entity_id": "US_SOFR_MARKET", "canonical_name": "U.S. Secured Overnight Financing Rate Market", "entity_type": "instrument", "target_role": "instrument", "market": "US Money Market", "country": "US", "exchange": None, "ticker": None, "currency": "USD", "confidence_score": 0.9, "mapping_method": "fred_money_market_rule", "aliases": [code, title, "SOFR"]}
    if "crude oil" in title_l or code in {"DCOILWTICO", "DCOILBRENTEU"}:
        commodity = "WTI Crude Oil" if "wti" in title_l or code == "DCOILWTICO" else "Brent Crude Oil"
        entity_id = _safe_token(commodity) + "_COMMODITY"
        return {"entity_id": entity_id, "canonical_name": commodity, "entity_type": "commodity", "target_role": "instrument", "market": "Global", "country": None, "exchange": None, "ticker": code, "currency": "USD", "confidence_score": 0.86, "mapping_method": "fred_commodity_title_rule", "aliases": [code, title, commodity]}
    return {"entity_id": "USA_COUNTRY", "canonical_name": "United States", "entity_type": "country", "target_role": "applies_to", "market": "US", "country": "USA", "exchange": None, "ticker": None, "currency": None, "confidence_score": 0.78, "mapping_method": "fred_default_us_macro_rule", "aliases": ["USA", "US", "United States"]}


def _fred_target_entity(target: dict[str, Any], code: str) -> dict[str, Any]:
    return {
        "entity_id": target.get("entity_id"),
        "canonical_name": target.get("canonical_name") or target.get("entity_id"),
        "entity_type": target.get("entity_type") or "instrument",
        "market": target.get("market"),
        "country": target.get("country"),
        "exchange": target.get("exchange"),
        "ticker": target.get("ticker"),
        "cik": None,
        "isin": None,
        "currency": target.get("currency"),
        "fiscal_year_end": None,
        "industry": target.get("industry") or "FRED target entity",
    }


def _treasury_maturity_label(code: str, title: str) -> str | None:
    code = code.upper()
    if code.startswith("DGS") and len(code) > 3:
        suffix = code[3:]
        if suffix.endswith("MO") and suffix[:-2].isdigit():
            return f"{suffix[:-2]}M"
        if suffix.isdigit():
            return f"{suffix}Y"
    match = re.search(r"(\d+)\s*-?\s*(year|yr)\b", title, flags=re.IGNORECASE)
    if match and "treasury" in title.lower():
        return f"{match.group(1)}Y"
    match = re.search(r"(\d+)\s*-?\s*(month|mo)\b", title, flags=re.IGNORECASE)
    if match and "treasury" in title.lower():
        return f"{match.group(1)}M"
    return None


def _fred_market_hint(code: str, title: str) -> str | None:
    title_l = str(title).lower()
    if code.upper().startswith("DGS") or "treasury" in title_l:
        return "US Treasury"
    if "exchange rate" in title_l:
        return "FX"
    if "oil" in title_l or "commodity" in title_l:
        return "Commodity"
    return "US" if _fred_default_us_series(code, title) else "Global"


def _fred_default_us_series(code: str, title: str) -> bool:
    title_l = str(title).lower()
    return code.upper() not in FRED_CURRENCY_PAIRS and any(token in title_l for token in ["united states", "u.s.", "federal", "treasury", "cpi", "gdp", "unemployment", "industrial production", "retail"])


def _add_relationship(
    relationships: dict[str, dict[str, Any]],
    subject_entity_id: str | None,
    relationship_type: str,
    object_id: str | None,
    object_type: str | None,
    object_entity_id: str | None,
    source_id: str | None,
    source_code: str | None,
    confidence_score: float,
    notes: dict[str, Any] | None = None,
) -> None:
    if not subject_entity_id or not relationship_type or not object_id:
        return
    relationship_id = _relationship_id(subject_entity_id, relationship_type, object_id, source_id, source_code)
    relationships[relationship_id] = {
        "relationship_id": relationship_id,
        "subject_entity_id": subject_entity_id,
        "relationship_type": relationship_type,
        "object_id": object_id,
        "object_type": object_type,
        "object_entity_id": object_entity_id,
        "source_id": source_id,
        "source_code": source_code,
        "confidence_score": confidence_score,
        "valid_from": None,
        "valid_to": None,
        "notes": notes or {},
    }


def _add_diagnostics(diagnostics: dict[str, Any], source_entities: list[dict[str, Any]], entity_by_id: dict[str, dict[str, Any]]) -> None:
    mapped_sources = set()
    for entity in entity_by_id.values():
        if entity.get("entity_type") == "company":
            mapped_sources.update(COMPANY_SOURCE_IDS)
        elif entity.get("entity_type") == "country":
            mapped_sources.add("worldbank_indicators")
        elif entity.get("entity_type") in {"currency_pair", "index"}:
            mapped_sources.add("fred_observations")
    for source_entity in source_entities:
        source_id = source_entity.get("source_id")
        metadata = _json_value(source_entity.get("raw_metadata"))
        if source_id == "worldbank_indicators" and isinstance(metadata, dict) and metadata.get("kind") == "indicator":
            continue
        if source_id == "fred_observations" and source_entity.get("source_code") not in {*FRED_CURRENCY_PAIRS, *FRED_INDEX_SERIES}:
            continue
        if source_id not in mapped_sources:
            diagnostics["unmapped_source_entities"].append({
                "source_id": source_id,
                "source_code": source_entity.get("source_code"),
                "source_name": source_entity.get("source_name"),
                "reason": "no high-confidence canonical entity rule yet",
            })
    diagnostics["notes"].append("FRED series are now modeled as fred_series entities with source_series_entity_map rows linking each series to its metric and applies_to/instrument target.")
    diagnostics["notes"].append("IMF DataMapper country codes are mapped to canonical country entities; countries missing from World Bank metadata use ISO3 fallback names until an ISO metadata enrichment pass is added.")


def _upsert_entity(entity_by_id: dict[str, dict[str, Any]], entity: dict[str, Any]) -> None:
    existing = entity_by_id.get(entity["entity_id"])
    if not existing:
        entity_by_id[entity["entity_id"]] = entity
        return
    for key, value in entity.items():
        if existing.get(key) in {None, ""} and value not in {None, ""}:
            existing[key] = value


def _add_alias(
    alias_by_id: dict[str, dict[str, Any]],
    entity_id: str,
    source_id: str | None,
    source_code: str | None,
    source_name: str | None,
    alias: Any,
    confidence_score: float,
) -> None:
    alias_text = str(alias).strip() if alias is not None else ""
    if not alias_text:
        return
    alias_id = _alias_id(entity_id, source_id, source_code, alias_text)
    existing = alias_by_id.get(alias_id)
    row = {
        "alias_id": alias_id,
        "entity_id": entity_id,
        "source_id": source_id,
        "source_code": source_code,
        "source_name": source_name,
        "alias": alias_text,
        "confidence_score": confidence_score,
    }
    if not existing or confidence_score > existing.get("confidence_score", 0):
        alias_by_id[alias_id] = row


def _alias_id(entity_id: str, source_id: str | None, source_code: str | None, alias: str) -> str:
    digest = hashlib.sha1(f"{entity_id}|{source_id}|{source_code or ''}|{alias.lower()}".encode("utf-8")).hexdigest()[:16]
    return f"alias_{digest}"



def _json_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _safe_token(value: Any) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "_", str(value or "").upper()).strip("_")
    return text or "UNKNOWN"


def _security_id(ticker: Any, exchange: Any, security_type: str) -> str:
    return f"SECURITY_{_safe_token(ticker)}_{_safe_token(exchange or 'UNKNOWN')}_{_safe_token(security_type)}"


def _relationship_id(subject_entity_id: str, relationship_type: str, object_id: str, source_id: str | None, source_code: str | None) -> str:
    digest = hashlib.sha1(f"{subject_entity_id}|{relationship_type}|{object_id}|{source_id or ''}|{source_code or ''}".encode("utf-8")).hexdigest()[:16]
    return f"rel_{digest}"


def _series_map_id(source_id: str, series_id: str) -> str:
    digest = hashlib.sha1(f"{source_id}|{series_id}".encode("utf-8")).hexdigest()[:16]
    return f"seriesmap_{digest}"

def _json_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _cik10(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.upper().startswith("CIK"):
        text = text[3:]
    if not text.isdigit():
        return None
    return text.zfill(10)


def _upper(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text.upper() if text else None


def _clean_code(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None



def _short_company_alias(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    cleaned = re.sub(r"\s*/.*$", "", text)
    cleaned = re.sub(
        r"\b(incorporated|inc|corp|corporation|co|company|ltd|limited|plc|group|holdings)\.?$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip(" ,.-")
    return cleaned if cleaned and cleaned.lower() != text.lower() else None

def _cn_exchange_from_selector(selector: Any) -> str | None:
    text = str(selector or "")
    if "gssz" in text:
        return "SZSE"
    if "gssh" in text:
        return "SSE"
    if "bj" in text.lower():
        return "BSE"
    return None


def _cn_exchange_from_metadata(metadata: Any) -> str | None:
    if not isinstance(metadata, dict):
        return None
    page_column = str(metadata.get("pageColumn") or "")
    org_id = str(metadata.get("orgId") or "")
    if page_column.startswith("SZ") or org_id.startswith("gssz"):
        return "SZSE"
    if page_column.startswith("SH") or org_id.startswith("gssh"):
        return "SSE"
    if page_column.startswith("BJ"):
        return "BSE"
    return None


def _cn_industry_from_metadata(metadata: Any) -> str | None:
    if not isinstance(metadata, dict):
        return None
    pool_metadata = metadata.get("pool_metadata")
    if isinstance(pool_metadata, dict) and pool_metadata.get("industry"):
        return str(pool_metadata["industry"])
    source_row = metadata.get("source_row")
    if isinstance(source_row, dict):
        for field in ("CSRC_CODE_DESC", "xxhyzl", "industry"):
            if source_row.get(field):
                return str(source_row[field])
    for field in ("industry", "CSRC_CODE_DESC", "xxhyzl"):
        if metadata.get(field):
            return str(metadata[field])
    return None


def _markdown_report(report: dict[str, Any]) -> str:
    lines = ["# Entity Normalization Report", ""]
    lines.append(f"Canonical entities: {report['canonical_entity_count']}")
    lines.append(f"Aliases: {report['alias_count']}")
    lines.append("")
    lines.append("## Entity Types")
    lines.append("")
    for entity_type, count in report.get("entity_type_counts", {}).items():
        lines.append(f"- {entity_type}: {count}")
    lines.append("")
    lines.append("## Samples")
    lines.append("")
    lines.append("| entity_id | name | type | market | ticker | cik |")
    lines.append("|---|---|---|---|---|---|")
    for entity in report.get("sample_entities", [])[:20]:
        lines.append(
            "| {entity_id} | {canonical_name} | {entity_type} | {market} | {ticker} | {cik} |".format(
                entity_id=entity.get("entity_id") or "",
                canonical_name=str(entity.get("canonical_name") or "").replace("|", "\\|"),
                entity_type=entity.get("entity_type") or "",
                market=entity.get("market") or "",
                ticker=entity.get("ticker") or "",
                cik=entity.get("cik") or "",
            )
        )
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    for note in report.get("diagnostics", {}).get("notes", []):
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)
