from __future__ import annotations

import json
import re
import time
from datetime import date
from pathlib import Path
from typing import Any

import requests

BSE_BASE_URL = "https://www.bse.cn"
BSE_COMPANY_URL = f"{BSE_BASE_URL}/nqxxController/nqxxCnzq.do"
BSE_ANNOUNCEMENT_URL = (
    f"{BSE_BASE_URL}/disclosureInfoController/companyAnnouncement.do"
)
BSE_COMPANY_REFERER = f"{BSE_BASE_URL}/nq/listedcompany.html"
BSE_DISCLOSURE_REFERER = f"{BSE_BASE_URL}/disclosure/announcement.html"

BSE_CATEGORY_MAP: dict[str, tuple[str, tuple[str, ...]]] = {
    "annual": ("1", ("9503-1001", "9503-1005")),
    "semiannual": ("1", ("9503-1002", "9503-1006")),
    "q1": ("1", ("9503-1003", "9504-8001")),
    "q3": ("1", ("9503-1004", "9504-2106")),
}

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "Chrome/126 Safari/537.36 RawFinancialDataLake/0.1"
    )
}


class BsePublicSession:
    """HTTP session for BSE's public endpoints and one-step WAF cookie challenge."""

    def __init__(self) -> None:
        self.session = requests.Session()

    def post(
        self,
        url: str,
        data: list[tuple[str, str]],
        *,
        referer: str,
        timeout: float = 60.0,
    ) -> requests.Response:
        headers = {**_DEFAULT_HEADERS, "Referer": referer}
        response = self.session.post(
            url,
            data=data,
            headers=headers,
            allow_redirects=False,
            timeout=timeout,
        )
        if response.status_code in {302, 307}:
            location = response.headers.get("Location", "")
            if location and location.rstrip("/") != url.rstrip("/"):
                raise RuntimeError(f"Unexpected BSE redirect: {location}")
            response = self.session.post(
                url,
                data=data,
                headers=headers,
                allow_redirects=False,
                timeout=timeout,
            )
        if response.status_code in {302, 307}:
            raise RuntimeError("BSE public endpoint cookie handshake did not complete")
        return response

    def get(
        self,
        url: str,
        *,
        referer: str,
        timeout: float = 120.0,
    ) -> requests.Response:
        headers = {**_DEFAULT_HEADERS, "Referer": referer}
        response: requests.Response | None = None
        for attempt in range(4):
            if attempt:
                time.sleep(float(attempt))
                self.session = requests.Session()
            else:
                time.sleep(0.5)
            response = self.session.get(
                url,
                headers=headers,
                allow_redirects=False,
                timeout=timeout,
            )
            if response.status_code in {302, 307}:
                location = response.headers.get("Location", "")
                if location and location.rstrip("/") != url.rstrip("/"):
                    raise RuntimeError(f"Unexpected BSE PDF redirect: {location}")
                response = self.session.get(
                    url,
                    headers=headers,
                    allow_redirects=False,
                    timeout=timeout,
                )
            if response.status_code not in {302, 307, 403, 429}:
                return response
        assert response is not None
        if response.status_code in {302, 307}:
            raise RuntimeError("BSE PDF cookie handshake did not complete")
        return response


def parse_jsonp(payload: str) -> Any:
    text = payload.strip()
    if text.startswith(("[", "{")):
        return json.loads(text)
    start = text.find("(")
    end = text.rfind(")")
    if start < 0 or end <= start:
        raise ValueError("Invalid JSONP payload")
    return json.loads(text[start + 1 : end])


def discover_bse_companies(
    *,
    max_pages: int = 0,
    session: BsePublicSession | None = None,
) -> list[dict[str, Any]]:
    client = session or BsePublicSession()
    companies: list[dict[str, Any]] = []
    page = 0
    total_pages = 1
    while page < total_pages and (not max_pages or page < max_pages):
        response = client.post(
            BSE_COMPANY_URL,
            [
                ("page", str(page)),
                ("typejb", "T"),
                ("xxfcbj[]", "2"),
                ("xxzqdm", ""),
                ("sortfield", "xxzqdm"),
                ("sorttype", "asc"),
                ("callback", "finraw"),
            ],
            referer=BSE_COMPANY_REFERER,
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"BSE company directory failed: HTTP {response.status_code}"
            )
        payload = parse_jsonp(response.text)
        page_data = payload[0] if isinstance(payload, list) and payload else {}
        total_pages = int(page_data.get("totalPages") or 0)
        for row in page_data.get("content") or []:
            code = str(row.get("xxzqdm") or "").strip()
            name = str(row.get("xxzqjc") or "").strip()
            if not code or not name:
                continue
            companies.append(
                {
                    "stock_code": code,
                    "company_name": name,
                    "market": "BSE",
                    "board": "BSE",
                    "industry": str(row.get("xxhyzl") or "unknown").strip(),
                    "region": str(row.get("xxssdq") or "").strip() or None,
                    "listing_date": _compact_date(row.get("fxssrq")),
                    "source_provider": "BSE",
                    "source_url": BSE_COMPANY_URL,
                    "source_row": row,
                }
            )
        page += 1
    return companies


def discover_bse_announcements(
    *,
    stock_code: str,
    start_date: str,
    end_date: str,
    category: str = "annual",
    max_pages: int = 0,
    session: BsePublicSession | None = None,
) -> list[dict[str, Any]]:
    client = session or BsePublicSession()
    try:
        disclosure_type, subtypes = BSE_CATEGORY_MAP[category]
    except KeyError as exc:
        raise ValueError(f"Unsupported BSE report category: {category}") from exc
    fields = (
        "companyCd",
        "companyName",
        "disclosureTitle",
        "disclosurePostTitle",
        "destFilePath",
        "publishDate",
        "xxfcbj",
        "fileExt",
        "xxzrlx",
    )
    announcements: list[dict[str, Any]] = []
    page = 0
    total_pages = 1
    while page < total_pages and (not max_pages or page < max_pages):
        form: list[tuple[str, str]] = [
            ("disclosureType", disclosure_type),
            *[("disclosureSubtype[]", subtype) for subtype in subtypes],
            ("page", str(page)),
            ("companyCd", stock_code),
            ("isNewThree", "1"),
            ("startTime", start_date),
            ("endTime", end_date),
            ("keyword", ""),
            ("xxfcbj[]", "2"),
            ("hyType", ""),
            *[("needFields[]", field) for field in fields],
        ]
        response = client.post(
            BSE_ANNOUNCEMENT_URL,
            form,
            referer=BSE_DISCLOSURE_REFERER,
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"BSE announcement query failed: HTTP {response.status_code}"
            )
        payload = parse_jsonp(response.text)
        root = payload[0] if isinstance(payload, list) and payload else {}
        page_data = root.get("listInfo") or {}
        total_pages = int(page_data.get("totalPages") or 0)
        for row in page_data.get("content") or []:
            path = str(row.get("destFilePath") or "").strip()
            if not path:
                continue
            title = (
                str(row.get("disclosureTitle") or "")
                + str(row.get("disclosurePostTitle") or "")
            ).strip()
            announcements.append(
                {
                    "announcement_id": Path(path).stem,
                    "stock_code": stock_code,
                    "disclosed_stock_code": str(row.get("companyCd") or "").strip(),
                    "company_name": str(row.get("companyName") or "").strip(),
                    "title": title,
                    "year": _infer_report_year(title, row.get("publishDate")),
                    "report_type": category,
                    "market": "BSE",
                    "publish_date": str(row.get("publishDate") or "")[:10] or None,
                    "filename": Path(path).name,
                    "url": f"{BSE_BASE_URL}/{path.lstrip('/')}",
                    "source_row": row,
                }
            )
        page += 1
    return announcements


def discover_bse_from_strategy(strategy: dict[str, Any]) -> list[dict[str, Any]]:
    config = strategy.get("bse", {})
    categories = config.get("categories", ["annual"])
    excluded = tuple(
        str(value)
        for value in dict(config.get("selection_policy") or {}).get(
            "exclude_title_keywords", []
        )
        if str(value)
    )
    client = BsePublicSession()
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for company in config.get("stock_pool", []):
        code = str(company.get("stock_code") or "").strip()
        for category in categories:
            rows = discover_bse_announcements(
                stock_code=code,
                start_date=str(config["start_date"]),
                end_date=str(config["end_date"]),
                category=str(category),
                max_pages=int(config.get("max_pages", 0) or 0),
                session=client,
            )
            for row in rows:
                if any(keyword in row["title"] for keyword in excluded):
                    continue
                row["pool_metadata"] = company
                identity = str(row.get("announcement_id") or row["url"])
                if identity in seen:
                    continue
                seen.add(identity)
                output.append(row)
    return output


def write_bse_config(path: str, announcements: list[dict[str, Any]]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {"bse": {"announcements": announcements}},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return output


def _infer_report_year(title: str, publish_date: Any) -> str:
    match = re.search(r"(20\d{2})\s*年(?:年度)?报告", title)
    if match:
        return match.group(1)
    published = str(publish_date or "")
    if len(published) >= 4 and published[:4].isdigit():
        return str(int(published[:4]) - 1)
    return "unknown"


def _compact_date(value: Any) -> str | None:
    text = str(value or "").strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return text[:10] or None


def default_bse_end_date() -> str:
    return date.today().isoformat()
