from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict, deque
from datetime import date
from pathlib import Path
from typing import Any

import requests

from finraw.bse_discovery import (
    BSE_COMPANY_URL,
    discover_bse_companies,
)

SSE_COMPANY_URL = "https://query.sse.com.cn/sseQuery/commonQuery.do"
SSE_COMPANY_PAGE = "https://www.sse.com.cn/assortment/stock/list/share/"
SZSE_COMPANY_URL = "https://www.szse.cn/api/report/ShowReport/data"
SZSE_COMPANY_PAGE = "https://www.szse.cn/market/stock/company/"

INDUSTRY_CODES = tuple("ABCDEFGHIJKLMNOPQR")


def discover_sse_companies(
    *,
    limit_per_industry_board: int = 20,
    session: requests.Session | None = None,
) -> list[dict[str, Any]]:
    client = session or requests.Session()
    output: list[dict[str, Any]] = []
    for stock_type, board in (("1", "SSE_MAIN"), ("8", "SSE_STAR")):
        for industry_code in INDUSTRY_CODES:
            params = {
                "STOCK_TYPE": stock_type,
                "REG_PROVINCE": "",
                "CSRC_CODE": industry_code,
                "STOCK_CODE": "",
                "sqlId": "COMMON_SSE_CP_GPJCTPZ_GPLB_GP_L",
                "COMPANY_STATUS": "2,4,5,7,8",
                "type": "inParams",
                "isPagination": "true",
                "pageHelp.cacheSize": "1",
                "pageHelp.beginPage": "1",
                "pageHelp.pageSize": str(max(limit_per_industry_board, 25)),
                "pageHelp.pageNo": "1",
            }
            response = client.get(
                SSE_COMPANY_URL,
                params=params,
                headers={
                    "User-Agent": "Mozilla/5.0 RawFinancialDataLake/0.1",
                    "Referer": SSE_COMPANY_PAGE,
                },
                timeout=60,
            )
            response.raise_for_status()
            payload = response.json()
            rows = ((payload.get("pageHelp") or {}).get("data") or [])[
                :limit_per_industry_board
            ]
            for row in rows:
                code = str(row.get("A_STOCK_CODE") or "").strip()
                name = str(row.get("COMPANY_ABBR") or "").strip()
                if not code or not name:
                    continue
                output.append(
                    {
                        "stock_code": code,
                        "company_name": name,
                        "legal_name": str(row.get("FULL_NAME") or "").strip() or None,
                        "market": "SSE",
                        "board": board,
                        "industry_code": str(
                            row.get("CSRC_CODE") or industry_code
                        ).strip(),
                        "industry": str(row.get("CSRC_CODE_DESC") or "").strip(),
                        "region": str(row.get("AREA_NAME_DESC") or "").strip() or None,
                        "listing_date": _compact_date(row.get("LIST_DATE")),
                        "source_provider": "SSE",
                        "source_url": SSE_COMPANY_URL,
                        "source_row": row,
                    }
                )
    return _deduplicate_companies(output)


def discover_szse_companies(
    *,
    limit_per_industry: int = 20,
    session: requests.Session | None = None,
) -> list[dict[str, Any]]:
    client = session or requests.Session()
    output: list[dict[str, Any]] = []
    for industry_code in INDUSTRY_CODES:
        response = client.get(
            SZSE_COMPANY_URL,
            params={
                "SHOWTYPE": "JSON",
                "CATALOGID": "1110",
                "TABKEY": "tab1",
                "PAGENO": "1",
                "selectHylb": industry_code,
            },
            headers={
                "User-Agent": "Mozilla/5.0 RawFinancialDataLake/0.1",
                "Referer": SZSE_COMPANY_PAGE,
            },
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        tab = payload[0] if isinstance(payload, list) and payload else {}
        for row in (tab.get("data") or [])[:limit_per_industry]:
            code = str(row.get("agdm") or "").strip()
            name = _clean_html(str(row.get("agjc") or ""))
            if not code or not name:
                continue
            industry = str(row.get("sshymc") or "").strip()
            output.append(
                {
                    "stock_code": code,
                    "company_name": name,
                    "market": "SZSE",
                    "board": _szse_board(row.get("bk"), code),
                    "industry_code": industry[:1] or industry_code,
                    "industry": industry[2:].strip() if len(industry) > 2 else industry,
                    "region": None,
                    "listing_date": str(row.get("agssrq") or "")[:10] or None,
                    "source_provider": "SZSE",
                    "source_url": SZSE_COMPANY_URL,
                    "source_row": row,
                }
            )
    return _deduplicate_companies(output)


def build_a_share_universe(
    *,
    sse_count: int = 45,
    szse_count: int = 40,
    bse_count: int = 15,
) -> dict[str, Any]:
    if sse_count + szse_count + bse_count < 100:
        raise ValueError("A-share universe must contain at least 100 companies")
    today_value = date.today()
    bse_history_cutoff = date(today_value.year - 5, 12, 31).isoformat()
    sse = _stratified_select(discover_sse_companies(), sse_count)
    szse = _stratified_select(discover_szse_companies(), szse_count)
    bse_candidates = [
        company
        for company in discover_bse_companies()
        if str(company.get("listing_date") or "9999-12-31")
        <= bse_history_cutoff
    ]
    bse = _stratified_select(bse_candidates, bse_count)
    selected = [*sse, *szse, *bse]
    if len(selected) != sse_count + szse_count + bse_count:
        raise RuntimeError(
            "Authoritative company directories did not provide enough eligible "
            "companies for the requested quotas"
        )
    today = today_value.isoformat()
    return {
        "universe": {
            "universe_id": "cn_a_share_authoritative_100_v1",
            "as_of_date": today,
            "selection_method": "deterministic_round_robin_by_exchange_and_industry",
            "eligibility_policy": {
                "exclude_special_treatment_and_delisting_names": True,
                "bse_listing_date_on_or_before": bse_history_cutoff,
                "minimum_completed_annual_reports": 5,
            },
            "requested_counts": {
                "SSE": sse_count,
                "SZSE": szse_count,
                "BSE": bse_count,
            },
            "actual_counts": {
                "SSE": len(sse),
                "SZSE": len(szse),
                "BSE": len(bse),
            },
            "company_count": len(selected),
            "industry_count": len(
                {str(row.get("industry") or "unknown") for row in selected}
            ),
            "source_contract": {
                "SSE": SSE_COMPANY_URL,
                "SZSE": SZSE_COMPANY_URL,
                "BSE": BSE_COMPANY_URL,
            },
            "universe_hash": _universe_hash(selected),
        },
        "cninfo": {
            "start_date": "2020-01-01",
            "end_date": today,
            "categories": ["annual"],
            "max_pages": 2,
            "page_size": 30,
            "selection_policy": {
                "authority": "CNInfo official disclosure platform",
                "exclude_title_keywords": ["摘要", "英文", "H股", "取消", "已取消"],
                "keep_revision_versions": True,
                "minimum_annual_years": 5,
            },
            "stock_pool": [*sse, *szse],
        },
        "bse": {
            "start_date": "2020-01-01",
            "end_date": today,
            "categories": ["annual"],
            "max_pages": 2,
            "selection_policy": {
                "authority": "Beijing Stock Exchange official disclosure",
                "exclude_title_keywords": ["摘要", "取消", "已取消"],
                "keep_revision_versions": True,
                "minimum_annual_years": 5,
                "minimum_listing_history_years": 5,
            },
            "stock_pool": bse,
        },
    }


def write_a_share_universe(path: str, universe: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(universe, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output


def assemble_cn_expansion_profile(
    *,
    universe_path: str,
    cninfo_manifest_path: str,
    bse_manifest_path: str,
    extends: str = "prod_phase1_with_cninfo_generated.json",
) -> dict[str, Any]:
    universe = json.loads(Path(universe_path).read_text(encoding="utf-8"))
    cninfo_manifest = json.loads(
        Path(cninfo_manifest_path).read_text(encoding="utf-8")
    )
    bse_manifest = json.loads(
        Path(bse_manifest_path).read_text(encoding="utf-8")
    )
    cninfo = dict(universe.get("cninfo") or {})
    bse = dict(universe.get("bse") or {})
    cninfo["announcements"] = list(
        dict(cninfo_manifest.get("cninfo") or {}).get("announcements") or []
    )
    bse["announcements"] = list(
        dict(bse_manifest.get("bse") or {}).get("announcements") or []
    )
    cninfo_coverage = _validate_annual_report_coverage("cninfo", cninfo)
    bse_coverage = _validate_annual_report_coverage("bse", bse)
    return {
        "extends": extends,
        "greater_china_expansion": {
            "universe": universe.get("universe") or {},
            "qa_generation_enabled": False,
            "coverage_contract": {
                "minimum_annual_years_per_company": 5,
                "cninfo": cninfo_coverage,
                "bse": bse_coverage,
            },
        },
        "cninfo": cninfo,
        "bse": bse,
    }


def write_cn_expansion_profile(path: str, profile: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(profile, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output


def _validate_annual_report_coverage(
    source_name: str,
    source_config: dict[str, Any],
) -> dict[str, Any]:
    pool_codes = {
        str(row.get("stock_code") or "").strip()
        for row in source_config.get("stock_pool") or []
        if str(row.get("stock_code") or "").strip()
    }
    years_by_code: dict[str, set[str]] = defaultdict(set)
    for row in source_config.get("announcements") or []:
        code = str(row.get("stock_code") or "").strip()
        year = str(row.get("year") or "").strip()
        if code not in pool_codes:
            raise ValueError(
                f"{source_name} announcement references an out-of-scope company: {code}"
            )
        if re.fullmatch(r"20\d{2}", year):
            years_by_code[code].add(year)
    required_years = int(
        dict(source_config.get("selection_policy") or {}).get(
            "minimum_annual_years", 5
        )
    )
    insufficient = {
        code: sorted(years_by_code.get(code, set()))
        for code in sorted(pool_codes)
        if len(years_by_code.get(code, set())) < required_years
    }
    if insufficient:
        details = "; ".join(
            f"{code}={','.join(years) or 'none'}"
            for code, years in list(insufficient.items())[:20]
        )
        raise ValueError(
            f"{source_name} annual-report coverage is below {required_years} years: "
            + details
        )
    return {
        "company_count": len(pool_codes),
        "announcement_count": len(source_config.get("announcements") or []),
        "minimum_observed_years": min(
            (len(years_by_code[code]) for code in pool_codes), default=0
        ),
        "maximum_observed_years": max(
            (len(years_by_code[code]) for code in pool_codes), default=0
        ),
    }


def _stratified_select(
    companies: list[dict[str, Any]], requested_count: int
) -> list[dict[str, Any]]:
    groups: dict[str, deque[dict[str, Any]]] = defaultdict(deque)
    for company in sorted(companies, key=lambda row: str(row["stock_code"])):
        name = str(company.get("company_name") or "")
        if not _eligible_company_name(name):
            continue
        industry = str(
            company.get("industry_code") or company.get("industry") or "unknown"
        )
        groups[industry].append(company)
    selected: list[dict[str, Any]] = []
    industry_keys = sorted(groups)
    while len(selected) < requested_count:
        added = False
        for industry in industry_keys:
            if groups[industry]:
                selected.append(groups[industry].popleft())
                added = True
                if len(selected) == requested_count:
                    break
        if not added:
            break
    return selected


def _eligible_company_name(name: str) -> bool:
    normalized = name.upper().replace(" ", "")
    return (
        bool(normalized)
        and not normalized.startswith(("*ST", "ST"))
        and "退" not in normalized
    )


def _deduplicate_companies(
    companies: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return list(
        {
            (str(row["market"]), str(row["stock_code"])): row
            for row in companies
        }.values()
    )


def _universe_hash(companies: list[dict[str, Any]]) -> str:
    identity = [
        (str(row["market"]), str(row["stock_code"]))
        for row in sorted(
            companies,
            key=lambda row: (str(row["market"]), str(row["stock_code"])),
        )
    ]
    return hashlib.sha256(
        json.dumps(identity, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _clean_html(value: str) -> str:
    return re.sub(r"<[^>]+>", "", value).replace("&nbsp;", " ").strip()


def _compact_date(value: Any) -> str | None:
    text = str(value or "").strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return text[:10] or None


def _szse_board(value: Any, stock_code: str) -> str:
    text = str(value or "")
    if "创业" in text or stock_code.startswith("3"):
        return "SZSE_CHINEXT"
    return "SZSE_MAIN"
