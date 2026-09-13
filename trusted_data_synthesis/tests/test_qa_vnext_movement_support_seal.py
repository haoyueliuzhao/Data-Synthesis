"""Lossless evidence compression is not data deletion or re-selection."""

import gzip

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_movement_support import protocol, seal


def test_lossless_deterministic_gzip_retains_original(tmp_path):
    source = tmp_path / "original.json"
    protocol.write_once(source, {"中文": list(range(100))})
    a, b = tmp_path / "a.gz", tmp_path / "b.gz"
    first = seal.compress_once(source, a)
    second = seal.compress_once(source, b)
    assert a.read_bytes() == b.read_bytes()
    assert gzip.decompress(a.read_bytes()) == source.read_bytes()
    assert first["canonical_sha256"] == protocol.sha(source)
    assert first["published_sha256"] == second["published_sha256"]
    assert first["uncompressed_original_retained_locally"]


def test_gzip_never_overwrites(tmp_path):
    source, target = tmp_path / "source.json", tmp_path / "target.gz"
    protocol.write_once(source, {})
    seal.compress_once(source, target)
    with pytest.raises(FileExistsError):
        seal.compress_once(source, target)


def test_gzip_does_not_follow_symlinks(tmp_path):
    source = tmp_path / "source.json"
    protocol.write_once(source, {})
    link = tmp_path / "link"
    link.symlink_to(source)
    with pytest.raises(ValueError, match="compression_no_symlink"):
        seal.compress_once(link, tmp_path / "target.gz")


def test_publication_allowlist_only_final_diagnostic_artifacts():
    assert len(seal.JSON_FILES) == len(set(seal.JSON_FILES))
    assert seal.COMPRESS <= set(seal.JSON_FILES)
    assert all("/" not in x and ".." not in x for x in seal.JSON_FILES)
    assert "phase_zero_summary.json" in seal.JSON_FILES
    assert not any("session.json" in x or ".env" in x for x in seal.JSON_FILES)


@pytest.mark.parametrize("flag", ["failures", "errors", "skipped"])
def test_seal_rejects_nonpassing_tests(flag):
    raw = f'<testsuites><testsuite tests="2" {flag}="1" /></testsuites>'.encode()
    with pytest.raises(ValueError, match="complete_passing_CPU_tests"):
        seal.validate_junit(raw)


def test_seal_checks_full_junit_count():
    value = seal.validate_junit(b'<testsuites><testsuite tests="2" time="0.5" /></testsuites>')
    assert value == {"tests": 2, "failures": 0, "errors": 0, "skipped": 0, "junit_seconds": 0.5}
