from __future__ import annotations

from types import SimpleNamespace

from finraw.connectors import worldbank
from finraw.connectors.worldbank import WorldBankConnector


def test_worldbank_retries_transient_http_400(monkeypatch, tmp_path):
    responses = iter(
        [
            SimpleNamespace(status=400, content=b"<html>Request Error</html>", headers={}),
            SimpleNamespace(status=200, content=b'[{"pages":1},[]]', headers={}),
        ]
    )
    monkeypatch.setattr(worldbank, "get_url", lambda *_, **__: next(responses))
    monkeypatch.setattr(worldbank.time, "sleep", lambda *_: None)
    connector = object.__new__(WorldBankConnector)
    connector.dry_run = False
    connector.source_id = "worldbank_indicators"
    connector.snapshot_date = "2026-07-22"
    connector.db = SimpleNamespace(
        fetchone=lambda *_, **__: None,
    )
    captured = {}
    connector.save_raw_bytes = lambda **kwargs: captured.update(kwargs) or {
        "raw_object_id": "rawobj_ok"
    }

    result = connector._fetch_json(
        "job",
        "https://api.worldbank.org/v2/country/USA",
        {"format": "json"},
        str(tmp_path / "response.json"),
        "country metadata USA",
    )

    assert result["payload"] == [{"pages": 1}, []]
    assert captured["response_status"] == 200
    assert captured["validation_status"] == "passed"
