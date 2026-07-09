from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from finraw.db.client import DBProtocol


COMPANY_SOURCE_IDS = {"sec_companyfacts", "sec_submissions", "sec_filings", "cninfo_announcements"}

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
    entities, aliases, diagnostics = build_entity_normalization(db, config)
    db.execute("DELETE FROM entity_alias_map")
    db.execute("DELETE FROM canonical_entities")
    for entity in entities:
        db.execute(
            """
            INSERT INTO canonical_entities (
                entity_id, canonical_name, entity_type, market, country, exchange,
                ticker, cik, isin, currency, fiscal_year_end, industry
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            ],
        )
    for alias in aliases:
        db.execute(
            """
            INSERT INTO entity_alias_map (
                alias_id, entity_id, source_id, source_code, source_name, alias, confidence_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                alias.get("alias_id"),
                alias.get("entity_id"),
                alias.get("source_id"),
                alias.get("source_code"),
                alias.get("source_name"),
                alias.get("alias"),
                alias.get("confidence_score"),
            ],
        )
    report = {
        "canonical_entity_count": len(entities),
        "alias_count": len(aliases),
        "entity_type_counts": dict(sorted(Counter(entity["entity_type"] for entity in entities).items())),
        "market_counts": dict(sorted(Counter(entity.get("market") or "unknown" for entity in entities).items())),
        "diagnostics": diagnostics,
        "sample_entities": entities[:20],
        "sample_aliases": aliases[:30],
    }
    if output_dir:
        paths = write_entity_normalization_report(report, output_dir)
        report["written_files"] = [str(path) for path in paths]
    return report


def build_entity_normalization(db: DBProtocol, config: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    source_entities = [dict(row) for row in db.fetchall("SELECT * FROM source_entities")]
    raw_records = [dict(row) for row in db.fetchall("SELECT source_id, record_type, record_key, record_json, entity_hint, metric_hint FROM raw_records")]

    entity_by_id: dict[str, dict[str, Any]] = {}
    alias_by_id: dict[str, dict[str, Any]] = {}
    diagnostics: dict[str, Any] = {
        "unmapped_source_entities": [],
        "skipped_records": [],
        "notes": [],
    }

    _add_sec_companies(entity_by_id, alias_by_id, source_entities, raw_records, config)
    _add_cninfo_companies(entity_by_id, alias_by_id, source_entities, raw_records, config)
    _add_worldbank_countries(entity_by_id, alias_by_id, source_entities)
    _add_fred_entities(entity_by_id, alias_by_id, source_entities)
    _add_diagnostics(diagnostics, source_entities, entity_by_id)

    entities = sorted(entity_by_id.values(), key=lambda row: (row["entity_type"], row["entity_id"]))
    aliases = sorted(alias_by_id.values(), key=lambda row: (row["entity_id"], row.get("source_id") or "", row.get("alias") or ""))
    return entities, aliases, diagnostics


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
    for company in config.get("sec", {}).get("sample_companies", []):
        cik = _cik10(company.get("cik"))
        if cik:
            seen_ciks.add(cik)
        companies.append({
            "ticker": _upper(company.get("ticker")),
            "cik": cik,
            "name": company.get("name") or company.get("ticker"),
            "exchange": company.get("exchange"),
            "industry": company.get("industry"),
            "source": "config",
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
    for item in config.get("cninfo", {}).get("stock_pool", []):
        code = _clean_code(item.get("stock_code"))
        if not code:
            continue
        companies[code] = {
            "stock_code": code,
            "name": item.get("company_name") or code,
            "exchange": item.get("market") or _cn_exchange_from_selector(item.get("selector")),
            "source": "config",
        }
    for source_entity in source_entities:
        if source_entity.get("source_id") != "cninfo_announcements":
            continue
        code = _clean_code(source_entity.get("source_code"))
        if not code:
            continue
        metadata = _json_value(source_entity.get("raw_metadata"))
        companies.setdefault(code, {
            "stock_code": code,
            "name": source_entity.get("source_name") or (metadata.get("secName") if isinstance(metadata, dict) else None) or code,
            "exchange": _cn_exchange_from_metadata(metadata),
            "source": "source_entities",
        })
    for record in raw_records:
        if record.get("record_type") != "cninfo_pdf_announcement":
            continue
        payload = _json_value(record.get("record_json"))
        if not isinstance(payload, dict):
            continue
        code = _clean_code(payload.get("stock_code"))
        if not code:
            continue
        companies.setdefault(code, {
            "stock_code": code,
            "name": payload.get("company_name") or payload.get("source_row", {}).get("secName") or code,
            "exchange": _cn_exchange_from_metadata(payload.get("source_row")),
            "source": "raw_records",
        })

    for company in companies.values():
        code = company["stock_code"]
        exchange = company.get("exchange") or "CN"
        entity_id = f"{code}_{exchange}"
        _upsert_entity(entity_by_id, {
            "entity_id": entity_id,
            "canonical_name": company.get("name") or code,
            "entity_type": "company",
            "market": "CN",
            "country": "CN",
            "exchange": exchange,
            "ticker": code,
            "cik": None,
            "isin": None,
            "currency": "CNY",
            "fiscal_year_end": "12-31",
            "industry": None,
        })
        aliases = [code, company.get("name"), f"{code}.{exchange}" if exchange not in {"CN", None} else None]
        for alias in aliases:
            _add_alias(alias_by_id, entity_id, "cninfo_announcements", code, company.get("name"), alias, 0.96)


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


def _add_fred_entities(
    entity_by_id: dict[str, dict[str, Any]],
    alias_by_id: dict[str, dict[str, Any]],
    source_entities: list[dict[str, Any]],
) -> None:
    by_code = {source_entity.get("source_code"): source_entity for source_entity in source_entities if source_entity.get("source_id") == "fred_observations"}
    for code, spec in FRED_CURRENCY_PAIRS.items():
        source_entity = by_code.get(code, {})
        name = source_entity.get("source_name") or spec["canonical_name"]
        _upsert_entity(entity_by_id, {
            "entity_id": spec["entity_id"],
            "canonical_name": spec["canonical_name"],
            "entity_type": "currency_pair",
            "market": "Global",
            "country": None,
            "exchange": None,
            "ticker": code,
            "cik": None,
            "isin": None,
            "currency": spec["currency"],
            "fiscal_year_end": None,
            "industry": None,
        })
        for alias in [code, name, spec["canonical_name"], spec["currency"], spec["entity_id"].replace("_", "/")]:
            _add_alias(alias_by_id, spec["entity_id"], "fred_observations", code, name, alias, 0.92)

    for code, spec in FRED_INDEX_SERIES.items():
        source_entity = by_code.get(code, {})
        name = source_entity.get("source_name") or spec["canonical_name"]
        _upsert_entity(entity_by_id, {
            "entity_id": spec["entity_id"],
            "canonical_name": spec["canonical_name"],
            "entity_type": "index",
            "market": "US_Global",
            "country": "US",
            "exchange": None,
            "ticker": code,
            "cik": None,
            "isin": None,
            "currency": "USD",
            "fiscal_year_end": None,
            "industry": None,
        })
        for alias in [code, name, spec["canonical_name"]]:
            _add_alias(alias_by_id, spec["entity_id"], "fred_observations", code, name, alias, 0.9)


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
    diagnostics["notes"].append("World Bank indicator metadata and most FRED macro series are metrics, not canonical entities in this layer.")
    diagnostics["notes"].append("IMF raw responses are not observation-expanded yet, so no IMF canonical entities are generated in this pass.")


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

