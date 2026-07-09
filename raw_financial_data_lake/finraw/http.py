from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass
class HttpResponse:
    url: str
    status: int
    headers: dict[str, str]
    content: bytes

    def json(self) -> Any:
        return json.loads(self.content.decode("utf-8"))


def get_url(
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    retries: int = 2,
    backoff_seconds: float = 1.0,
    polite_delay_seconds: float = 0.0,
    timeout_seconds: float = 120.0,
) -> HttpResponse:
    if polite_delay_seconds > 0:
        time.sleep(polite_delay_seconds)

    final_url = url
    if params:
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        final_url = f"{url}?{query}"

    last_response: HttpResponse | None = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(final_url, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                response = HttpResponse(
                    url=final_url,
                    status=resp.status,
                    headers=dict(resp.headers.items()),
                    content=resp.read(),
                )
        except urllib.error.HTTPError as exc:
            response = HttpResponse(
                url=final_url,
                status=exc.code,
                headers=dict(exc.headers.items()),
                content=exc.read(),
            )
        except (urllib.error.URLError, TimeoutError):
            if attempt >= retries:
                raise
            time.sleep(backoff_seconds * (attempt + 1))
            continue

        last_response = response
        if response.status < 500 or attempt >= retries:
            return response
        time.sleep(backoff_seconds * (attempt + 1))

    assert last_response is not None
    return last_response



def post_form(
    url: str,
    data: dict[str, Any],
    headers: dict[str, str] | None = None,
    retries: int = 2,
    backoff_seconds: float = 1.0,
    polite_delay_seconds: float = 0.0,
    timeout_seconds: float = 120.0,
) -> HttpResponse:
    if polite_delay_seconds > 0:
        time.sleep(polite_delay_seconds)

    body = urllib.parse.urlencode({k: v for k, v in data.items() if v is not None}).encode("utf-8")
    request_headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "User-Agent": "Mozilla/5.0 RawFinancialDataLake/0.1",
        **(headers or {}),
    }
    last_response: HttpResponse | None = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=body, headers=request_headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                response = HttpResponse(
                    url=url,
                    status=resp.status,
                    headers=dict(resp.headers.items()),
                    content=resp.read(),
                )
        except urllib.error.HTTPError as exc:
            response = HttpResponse(
                url=url,
                status=exc.code,
                headers=dict(exc.headers.items()),
                content=exc.read(),
            )
        except (urllib.error.URLError, TimeoutError):
            if attempt >= retries:
                raise
            time.sleep(backoff_seconds * (attempt + 1))
            continue
        last_response = response
        if response.status < 500 or attempt >= retries:
            return response
        time.sleep(backoff_seconds * (attempt + 1))
    assert last_response is not None
    return last_response
