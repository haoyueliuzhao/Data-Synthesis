from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from finraw.http import post_form

CNINFO_QUERY_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_TOP_SEARCH_URL = "https://www.cninfo.com.cn/new/information/topSearch/query"
CNINFO_STATIC_BASE = "https://static.cninfo.com.cn/"
CNINFO_COLUMNS = {
    "SZSE": "szse",
    "SSE": "sse",
}

CATEGORY_MAP = {
    "annual": "category_ndbg_szsh",
    "semiannual": "category_bndbg_szsh",
    "q1": "category_yjdbg_szsh",
    "q3": "category_sjdbg_szsh",
}


def discover_cninfo_announcements(
    *,
    stock: str,
    start_date: str,
    end_date: str,
    category: str = "annual",
    page_size: int = 30,
    max_pages: int = 1,
    market: str | None = None,
) -> list[dict[str, Any]]:
    announcements: list[dict[str, Any]] = []
    category_value = CATEGORY_MAP.get(category, category)
    for page in range(1, max_pages + 1):
        form = {
            "pageNum": page,
            "pageSize": page_size,
            "column": _cninfo_column(market, stock),
            "tabName": "fulltext",
            "plate": "",
            "stock": stock,
            "searchkey": "",
            "secid": "",
            "category": category_value,
            "trade": "",
            "seDate": f"{start_date}~{end_date}",
            "sortName": "",
            "sortType": "",
            "isHLtitle": "true",
        }
        resp = post_form(
            CNINFO_QUERY_URL,
            form,
            headers={
                "Referer": "https://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search",
                "Origin": "https://www.cninfo.com.cn",
                "X-Requested-With": "XMLHttpRequest",
            },
            polite_delay_seconds=0.2,
        )
        if resp.status != 200:
            raise RuntimeError(f"CNInfo query failed: HTTP {resp.status}: {resp.content[:200]!r}")
        payload = resp.json()
        rows = payload.get("announcements") or []
        if not rows:
            break
        for row in rows:
            adjunct_url = row.get("adjunctUrl") or ""
            if not adjunct_url:
                continue
            stock_code = (row.get("secCode") or stock.split(",")[0].split("#")[-1]).strip()
            year = _infer_year(row, category)
            announcements.append(
                {
                    "announcement_id": row.get("announcementId"),
                    "stock_code": stock_code,
                    "market": str(market or _infer_market(stock_code)).upper(),
                    "company_name": row.get("secName"),
                    "title": _clean_title(row.get("announcementTitle")),
                    "year": year,
                    "report_type": category,
                    "publish_date": _format_announcement_time(row.get("announcementTime")),
                    "filename": Path(adjunct_url).name,
                    "url": CNINFO_STATIC_BASE + adjunct_url.lstrip("/"),
                    "source_row": row,
                }
            )
        if not payload.get("hasMore"):
            break
    return announcements


def write_cninfo_config(path: str, announcements: list[dict[str, Any]]) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"cninfo": {"announcements": announcements}}, ensure_ascii=False, indent=2) + "\n")
    return out


def resolve_cninfo_stock_selectors(
    stock_pool: list[dict[str, Any]],
) -> dict[tuple[str, str], str]:
    """Resolve CNInfo's exchange-specific orgId without guessing from stock codes."""
    resolved: dict[tuple[str, str], str] = {}
    missing: list[str] = []
    for stock in stock_pool:
        code = str(stock.get("stock_code") or "").strip()
        market = str(stock.get("market") or _infer_market(code)).upper()
        _cninfo_column(market, code)
        explicit = str(stock.get("selector") or "").strip()
        if explicit:
            selector_code, separator, org_id = explicit.partition(",")
            if separator and selector_code.strip() == code and org_id.strip():
                resolved[(market, code)] = f"{code},{org_id.strip()}"
                continue
            if separator:
                raise ValueError(
                    f"CNInfo selector does not match requested stock: {market}:{code}"
                )
        org_id = _resolve_org_id_from_top_search(code)
        if not org_id:
            org_id = _resolve_org_id_from_announcements(code, market)
        if code and org_id:
            resolved[(market, code)] = f"{code},{org_id}"
            continue
        missing.append(f"{market}:{code or '<missing>'}")
    if missing:
        raise ValueError(
            "CNInfo selectors could not be resolved for: " + ", ".join(sorted(missing))
        )
    return resolved


def _resolve_org_id_from_top_search(stock_code: str) -> str | None:
    if not stock_code:
        return None
    response = post_form(
        CNINFO_TOP_SEARCH_URL,
        {"keyWord": stock_code, "maxSecNum": 10, "maxListNum": 5},
        headers={
            "Referer": "https://www.cninfo.com.cn/",
            "X-Requested-With": "XMLHttpRequest",
        },
        polite_delay_seconds=0.2,
    )
    if response.status != 200:
        raise RuntimeError(
            f"CNInfo top-search failed for {stock_code}: HTTP {response.status}"
        )
    payload = response.json()
    rows = payload if isinstance(payload, list) else []
    org_ids = {
        str(row.get("orgId") or "").strip()
        for row in rows
        if str(row.get("code") or "").strip() == stock_code
        and not _boolean_value(row.get("delisted"))
        and str(row.get("orgId") or "").strip()
    }
    if len(org_ids) > 1:
        raise ValueError(
            f"CNInfo top-search returned multiple orgIds for {stock_code}: "
            + ", ".join(sorted(org_ids))
        )
    return next(iter(org_ids), None)


def _resolve_org_id_from_announcements(stock_code: str, market: str) -> str | None:
    """Resolve an orgId from CNInfo's official announcement search.

    CNInfo's former exchange stock registry endpoints now return 404. The
    announcement endpoint remains authoritative and includes both secCode and
    orgId. Exact code matching prevents a broad search result from silently
    binding the wrong issuer.
    """
    if not stock_code:
        return None
    form = {
        "pageNum": 1,
        "pageSize": 30,
        "column": _cninfo_column(market, stock_code),
        "tabName": "fulltext",
        "plate": "",
        "stock": "",
        "searchkey": stock_code,
        "secid": "",
        "category": "",
        "trade": "",
        "seDate": f"1990-01-01~{date.today().isoformat()}",
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true",
    }
    response = post_form(
        CNINFO_QUERY_URL,
        form,
        headers={
            "Referer": "https://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search",
            "Origin": "https://www.cninfo.com.cn",
            "X-Requested-With": "XMLHttpRequest",
        },
        polite_delay_seconds=0.2,
    )
    if response.status != 200:
        raise RuntimeError(
            f"CNInfo orgId lookup failed for {market}:{stock_code}: "
            f"HTTP {response.status}"
        )
    rows = dict(response.json()).get("announcements") or []
    org_ids = {
        str(row.get("orgId") or "").strip()
        for row in rows
        if str(row.get("secCode") or "").strip() == stock_code
        and str(row.get("orgId") or "").strip()
    }
    if len(org_ids) > 1:
        raise ValueError(
            f"CNInfo returned multiple orgIds for {market}:{stock_code}: "
            + ", ".join(sorted(org_ids))
        )
    return next(iter(org_ids), None)


def _cninfo_column(market: str | None, stock: str) -> str:
    stock_code = str(stock).split(",", 1)[0].strip()
    normalized_market = str(market or _infer_market(stock_code)).upper()
    try:
        return CNINFO_COLUMNS[normalized_market]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported CNInfo market for announcement discovery: {normalized_market}"
        ) from exc


def _infer_market(stock_code: str) -> str:
    return "SSE" if str(stock_code).startswith(("5", "6", "9")) else "SZSE"


def _boolean_value(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _infer_year(row: dict[str, Any], report_type: str) -> str:
    title = _clean_title(row.get("announcementTitle"))
    title_year = re.search(r"(?<!\d)(20\d{2})(?!\d)", title)
    if title_year:
        return title_year.group(1)

    publish_date = _format_announcement_time(row.get("announcementTime"))
    if not publish_date or not publish_date[:4].isdigit():
        return "unknown"
    publish_year = int(publish_date[:4])
    # Annual reports are normally filed in the following calendar year. Other
    # periodic reports use their publication year when the title omits a year.
    return str(publish_year - 1 if report_type == "annual" else publish_year)


def _clean_title(value: str | None) -> str:
    return (value or "").replace("<em>", "").replace("</em>", "").strip()



def _format_announcement_time(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        # CNInfo returns milliseconds since epoch for announcementTime.
        seconds = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(seconds, tz=timezone.utc).date().isoformat()
    text = str(value)
    return text[:10] if text else None



def discover_cninfo_from_strategy(strategy: dict[str, Any]) -> list[dict[str, Any]]:
    cninfo = strategy.get("cninfo", {})
    stock_pool = cninfo.get("stock_pool", [])
    categories = cninfo.get("categories", ["annual"])
    start_date = cninfo["start_date"]
    end_date = cninfo["end_date"]
    max_pages = int(cninfo.get("max_pages", 1))
    page_size = int(cninfo.get("page_size", 30))
    excluded = tuple(
        str(value)
        for value in dict(cninfo.get("selection_policy") or {}).get(
            "exclude_title_keywords", []
        )
        if str(value)
    )
    all_announcements: list[dict[str, Any]] = []
    seen: set[str] = set()
    selectors = resolve_cninfo_stock_selectors(stock_pool)
    for stock in stock_pool:
        stock_code = str(stock.get("stock_code") or "").strip()
        market = str(stock.get("market") or "SZSE").upper()
        selector = selectors.get((market, stock_code))
        if not selector:
            raise ValueError(f"Missing resolved CNInfo selector for {market}:{stock_code}")
        for category in categories:
            discovered = discover_cninfo_announcements(
                stock=selector,
                start_date=start_date,
                end_date=end_date,
                category=category,
                page_size=page_size,
                max_pages=max_pages,
                market=market,
            )
            for ann in discovered:
                if any(keyword in str(ann.get("title") or "") for keyword in excluded):
                    continue
                ann.setdefault("stock_code", stock.get("stock_code"))
                ann.setdefault("company_name", stock.get("company_name"))
                ann["pool_metadata"] = stock
                identity = str(ann.get("announcement_id") or ann.get("url") or "")
                if identity and identity not in seen:
                    seen.add(identity)
                    all_announcements.append(ann)
    return all_announcements
