from __future__ import annotations

from types import SimpleNamespace

from finraw.connectors.base import RawSourceConnector


class Connector(RawSourceConnector):
    def run(self) -> None:
        pass


def test_collision_safe_path_adds_content_hash_suffix(tmp_path):
    connector = object.__new__(Connector)
    connector.store = SimpleNamespace(root=tmp_path)
    connector.db = SimpleNamespace(
        fetchone=lambda *_args, **_kwargs: {"content_sha256": "old_hash"}
    )

    path = connector._collision_safe_relative_path(
        "worldbank/page=1.json", "abcdef1234567890"
    )

    assert path == "worldbank/page=1__sha256=abcdef123456.json"


def test_collision_safe_path_reuses_identical_content(tmp_path):
    connector = object.__new__(Connector)
    connector.store = SimpleNamespace(root=tmp_path)
    connector.db = SimpleNamespace(
        fetchone=lambda *_args, **_kwargs: {"content_sha256": "same_hash"}
    )

    path = connector._collision_safe_relative_path(
        "fred/series.json", "same_hash"
    )

    assert path == "fred/series.json"
