"""Lossless evidence packing controls, with no source deletion."""

import tarfile

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_probe_coverage import protocol as p
from trusted_synthesis.experiments.finance_qa_vnext_probe_coverage import publish


def test_exact_sorted_archive_and_originals_retained(tmp_path):
    a, b = tmp_path / "requests" / "a.json", tmp_path / "sessions" / "b.json"
    p.write_once(a, {"public": "中文"})
    p.write_once(b, {"probe_only": True})
    target = tmp_path / "raw.tar.gz"
    publish.pack_once(tmp_path, [a, b], target)
    with tarfile.open(target, "r:gz") as archive:
        assert archive.getnames() == ["requests/a.json", "sessions/b.json"]
        assert archive.extractfile("requests/a.json").read() == a.read_bytes()
    assert a.exists() and b.exists()
    with pytest.raises(ValueError):
        publish.pack_once(tmp_path, [a, b], target)


def test_unsorted_or_duplicate_members_are_rejected(tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    p.write_once(a, {})
    p.write_once(b, {})
    for paths in ([b, a], [a, a]):
        with pytest.raises(ValueError):
            publish.pack_once(tmp_path, paths, tmp_path / "out.tar.gz")


def test_no_wallet_or_runtime_in_direct_publication():
    assert not any("sqlite" in x or "runtime" in x or ".env" in x for x in publish.DIRECT)
    assert {"report.json", "freeze.json", "coverage_metrics.json"} <= publish.DIRECT
