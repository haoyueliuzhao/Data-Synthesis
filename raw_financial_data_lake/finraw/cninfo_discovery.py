from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from finraw.http import get_url, post_form

CNINFO_QUERY_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_STATIC_BASE = "https://static.cninfo.com.cn/"
CNINFO_STOCK_REGISTRY_URLS = {
    "SZSE": "https://www.cninfo.com.cn/new/data/szse_stock.json",
    "SSE": "https://www.cninfo.com.cn/new/data/sse_stock.json",
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
) -> list[dict[str, Any]]:
    announcements: list[dict[str, Any]] = []
    category_value = CATEGORY_MAP.get(category, category)
    for page in range(1, max_pages + 1):
        form = {
            "pageNum": page,
            "pageSize": page_size,
            "column": "szse",
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
            year = _infer_year(row)
            announcements.append(
                {
                    "announcement_id": row.get("announcementId"),
                    "stock_code": stock_code,
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
    requested_markets = {
        str(stock.get("market") or "SZSE").upper()
        for stock in stock_pool
        if "," not in str(stock.get("selector") or "")
    }
    registries: dict[str, dict[str, str]] = {}
    for market in sorted(requested_markets):
        url = CNINFO_STOCK_REGISTRY_URLS.get(market)
        if not url:
            raise ValueError(f"Unsupported CNInfo market for selector resolution: {market}")
        response = get_url(url, polite_delay_seconds=0.2)
        if response.status != 200:
            raise RuntimeError(
                f"CNInfo stock registry failed for {market}: HTTP {response.status}"
            )
        rows = dict(response.json()).get("stockList") or []
        registries[market] = {
            str(row.get("code") or "").strip(): str(row.get("orgId") or "").strip()
            for row in rows
            if row.get("code") and row.get("orgId")
        }

    resolved: dict[tuple[str, str], str] = {}
    missing: list[str] = []
    for stock in stock_pool:
        code = str(stock.get("stock_code") or "").strip()
        market = str(stock.get("market") or "SZSE").upper()
        explicit = str(stock.get("selector") or "").strip()
        if explicit and "," in explicit:
            resolved[(market, code)] = explicit
            continue
        org_id = registries.get(market, {}).get(code)
        if not code or not org_id:
            missing.append(f"{market}:{code or '<missing>'}")
            continue
        resolved[(market, code)] = f"{code},{org_id}"
    if missing:
        raise ValueError(
            "CNInfo selectors could not be resolved for: " + ", ".join(sorted(missing))
        )
    return resolved


def _infer_year(row: dict[str, Any]) -> str:
    title = _clean_title(row.get("announcementTitle"))
    for token in title.replace("年", " ").replace("年度", " ").split():
        if token.isdigit() and len(token) == 4:
            return token
    date = str(row.get("announcementTime") or "")[:4]
    return date if date.isdigit() else "unknown"


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
