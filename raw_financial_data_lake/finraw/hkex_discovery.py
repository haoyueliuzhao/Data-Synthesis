from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

HKEX_SECURITIES_WORKBOOK_URL = (
    "https://www.hkex.com.hk/eng/services/trading/securities/"
    "securitieslists/ListOfSecurities.xlsx"
)
HKEX_ACTIVE_STOCK_URL = (
    "https://www1.hkexnews.hk/ncms/script/eds/activestock_sehk_e.json"
)
HKEX_TITLE_SEARCH_URL = (
    "https://www1.hkexnews.hk/search/titlesearch.xhtml?lang=en"
)
HKEX_NEWS_BASE_URL = "https://www1.hkexnews.hk"

# Audited Main Board issuer codes. Every code is still resolved against the
# current HKEXnews active-stock registry before use; this list is not treated
# as an authoritative issuer master by itself.
HKEX_CURATED_MAIN_BOARD_CODES = (
    "00001",
    "00002",
    "00003",
    "00005",
    "00006",
    "00023",
    "00012",
    "00016",
    "00017",
    "00019",
    "00027",
    "00066",
    "00101",
    "00175",
    "00267",
    "00288",
    "00386",
    "00388",
    "00669",
    "00688",
    "00700",
    "00762",
    "00823",
    "00857",
    "00883",
    "00939",
    "00941",
    "00960",
    "00981",
    "01038",
    "01044",
    "01088",
    "01109",
    "01211",
    "01299",
    "01398",
    "01810",
    "02020",
    "02318",
    "03988",
)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 RawFinancialDataLake/0.1",
    "Referer": HKEX_TITLE_SEARCH_URL,
}


def discover_hkex_active_companies(
    *,
    requested_count: int = 40,
    codes: tuple[str, ...] = HKEX_CURATED_MAIN_BOARD_CODES,
    session: requests.Session | None = None,
) -> list[dict[str, Any]]:
    if requested_count < 30 or requested_count > 50:
        raise ValueError("HKEX company pool must contain 30 to 50 companies")
    if requested_count > len(codes):
        raise ValueError("Curated HKEX issuer set is smaller than requested_count")
    client = session or requests.Session()
    response = client.get(HKEX_ACTIVE_STOCK_URL, headers=_HEADERS, timeout=60)
    response.raise_for_status()
    rows = response.json()
    active_by_code = {
        str(row.get("c") or "").zfill(5): row
        for row in rows
        if isinstance(row, dict) and str(row.get("c") or "").strip()
    }
    selected: list[dict[str, Any]] = []
    missing: list[str] = []
    for code in codes[:requested_count]:
        row = active_by_code.get(code)
        if not row:
            missing.append(code)
            continue
        selected.append(
            {
                "stock_code": code,
                "company_name": str(row.get("n") or "").strip(),
                "market": "HK",
                "exchange": "HKEX",
                "board": "Main Board",
                "currency": "HKD",
                "hkex_stock_id": int(row["i"]),
                "hkex_security_id": row.get("s"),
                "source_provider": "HKEXnews",
                "source_url": HKEX_ACTIVE_STOCK_URL,
                "source_row": row,
            }
        )
    if missing:
        raise ValueError(
            "Curated HKEX issuers are not active in the official registry: "
            + ", ".join(missing)
        )
    return selected


def discover_hkex_annual_reports(
    *,
    company: dict[str, Any],
    start_date: str,
    end_date: str,
    session: requests.Session | None = None,
) -> list[dict[str, Any]]:
    client = session or requests.Session()
    payload = {
        "lang": "EN",
        "category": "0",
        "market": "SEHK",
        "searchType": "0",
        "documentType": "-1",
        "t1code": "-2",
        "t2Gcode": "-2",
        "t2code": "-2",
        "stockId": str(company["hkex_stock_id"]),
        "from": _compact_date(start_date),
        "to": _compact_date(end_date),
        "title": "Annual Report",
    }
    response = client.post(
        HKEX_TITLE_SEARCH_URL,
        data=payload,
        headers=_HEADERS,
        timeout=60,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")
    reports: list[dict[str, Any]] = []
    for anchor in soup.select('a[href*=".pdf"]'):
        table_row = anchor.find_parent("tr")
        if table_row is None:
            continue
        cells = table_row.find_all("td")
        if len(cells) < 4:
            continue
        headline = cells[3].select_one(".headline")
        headline_text = headline.get_text(" ", strip=True) if headline else ""
        title = anchor.get_text(" ", strip=True)
        if "[annual report" not in headline_text.lower():
            continue
        publish_date = _release_date(cells[0].get_text(" ", strip=True))
        report_year, year_derivation = _report_year(title, publish_date)
        if not report_year:
            continue
        stock_codes = set(re.findall(r"\d{5}", cells[1].get_text(" ", strip=True)))
        if company["stock_code"] not in stock_codes:
            continue
        href = str(anchor.get("href") or "").strip()
        if not href:
            continue
        document_url = urljoin(HKEX_NEWS_BASE_URL, href)
        reports.append(
            {
                "announcement_id": Path(href).stem,
                "stock_code": company["stock_code"],
                "company_name": company["company_name"],
                "title": title,
                "headline_category": headline_text,
                "year": report_year,
                "year_derivation": year_derivation,
                "report_type": "annual",
                "market": "HK",
                "exchange": "HKEX",
                "language": "en",
                "publish_date": publish_date,
                "filename": Path(href).name,
                "url": document_url,
                "request_contract": payload,
                "pool_metadata": company,
            }
        )
    return reports


def build_hkex_disclosure_config(
    *,
    requested_count: int = 40,
    start_date: str = "2020-01-01",
    end_date: str | None = None,
    minimum_annual_years: int = 5,
) -> dict[str, Any]:
    end = end_date or date.today().isoformat()
    client = requests.Session()
    companies = discover_hkex_active_companies(
        requested_count=requested_count,
        session=client,
    )
    announcements: list[dict[str, Any]] = []
    years_by_code: dict[str, set[str]] = defaultdict(set)
    for company in companies:
        rows = discover_hkex_annual_reports(
            company=company,
            start_date=start_date,
            end_date=end,
            session=client,
        )
        announcements.extend(rows)
        years_by_code[company["stock_code"]].update(row["year"] for row in rows)
    insufficient = {
        company["stock_code"]: sorted(years_by_code[company["stock_code"]])
        for company in companies
        if len(years_by_code[company["stock_code"]]) < minimum_annual_years
    }
    if insufficient:
        raise ValueError(
            "HKEX official annual-report coverage is below "
            f"{minimum_annual_years} years: "
            + "; ".join(
                f"{code}={','.join(years) or 'none'}"
                for code, years in insufficient.items()
            )
        )
    return {
        "hkex": {
            "authority": "HKEX and HKEXnews official public sources",
            "securities_workbook_url": HKEX_SECURITIES_WORKBOOK_URL,
            "active_stock_registry_url": HKEX_ACTIVE_STOCK_URL,
            "title_search_url": HKEX_TITLE_SEARCH_URL,
            "selection_method": (
                "audited_main_board_allowlist_resolved_against_active_registry"
            ),
            "start_date": start_date,
            "end_date": end,
            "minimum_annual_years": minimum_annual_years,
            "stock_pool": companies,
            "announcements": sorted(
                announcements,
                key=lambda row: (
                    row["stock_code"],
                    row["year"],
                    row["publish_date"] or "",
                    row["announcement_id"],
                ),
            ),
            "coverage": {
                "company_count": len(companies),
                "announcement_count": len(announcements),
                "minimum_observed_years": min(map(len, years_by_code.values())),
                "maximum_observed_years": max(map(len, years_by_code.values())),
            },
        }
    }


def write_hkex_config(path: str, config: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(config, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output


def assemble_hkex_expansion_profile(
    *,
    manifest_path: str,
    extends: str = "prod_cn_authoritative_expansion.json",
) -> dict[str, Any]:
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    hkex = dict(manifest.get("hkex") or {})
    companies = list(hkex.get("stock_pool") or [])
    announcements = list(hkex.get("announcements") or [])
    minimum_years = int(hkex.get("minimum_annual_years") or 5)
    years_by_code: dict[str, set[str]] = defaultdict(set)
    for row in announcements:
        years_by_code[str(row.get("stock_code") or "")].add(
            str(row.get("year") or "")
        )
    missing = [
        str(company.get("stock_code") or "")
        for company in companies
        if len(years_by_code[str(company.get("stock_code") or "")])
        < minimum_years
    ]
    if not 30 <= len(companies) <= 50:
        raise ValueError("HKEX production pool must contain 30 to 50 companies")
    if missing:
        raise ValueError(
            "HKEX production profile has insufficient official annual-report "
            f"coverage: {', '.join(missing)}"
        )
    coverage = {
        "company_count": len(companies),
        "announcement_count": len(announcements),
        "minimum_observed_years": min(map(len, years_by_code.values())),
        "maximum_observed_years": max(map(len, years_by_code.values())),
    }
    return {
        "extends": extends,
        "hkex": hkex,
        "greater_china_expansion": {
            "qa_generation_enabled": False,
            "coverage_contract": {
                "hkex": coverage,
                "minimum_annual_years_per_company": minimum_years,
                "minimum_graph_ready_ratio": 0.9,
            },
        },
    }


def write_hkex_expansion_profile(path: str, profile: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(profile, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output


def _compact_date(value: str) -> str:
    parsed = datetime.strptime(value, "%Y-%m-%d")
    return parsed.strftime("%Y%m%d")


def _release_date(value: str) -> str | None:
    match = re.search(r"(\d{2})/(\d{2})/(\d{4})", value)
    if not match:
        return None
    day, month, year = match.groups()
    return f"{year}-{month}-{day}"


def _report_year(title: str, publish_date: str | None) -> tuple[str | None, str]:
    range_match = re.search(
        r"(?<!\d)(20\d{2})\s*/\s*(?:(20)?(\d{2}))(?!\d)",
        title,
    )
    if range_match:
        century = range_match.group(2) or range_match.group(1)[:2]
        return f"{century}{range_match.group(3)}", "fiscal_year_range_end"
    year_match = re.search(r"(?<!\d)(20\d{2})(?!\d)", title)
    if year_match:
        return year_match.group(1), "title"
    if publish_date:
        return str(int(publish_date[:4]) - 1), "publish_year_minus_one"
    return None, "unknown"
