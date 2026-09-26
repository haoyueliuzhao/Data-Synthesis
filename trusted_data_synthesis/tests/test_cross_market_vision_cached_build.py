"""Synthetic cached-build revision: no real artifact extraction, build or network."""

import hashlib
import io
import tarfile

import pytest
import run_cross_market_vision_cached_build_20260927 as m


@pytest.fixture
def raw(tmp_path, monkeypatch):
    monkeypatch.setattr(m.base, "RAW", tmp_path)
    monkeypatch.setattr(m, "RAW", tmp_path / "new")
    m.RAW.mkdir()
    return m.RAW


def archive(path, *, links=None, extras=()):
    if links is None:
        links = [(name, target, tarfile.SYMTYPE) for name, target in m.SKIPPED_LINKS.items()]
    with tarfile.open(path, "w:gz") as stream:
        for suffix, data in [("setup.py", b"pass\n"), ("version.txt", b"0.22.1\n")]:
            member = tarfile.TarInfo(m.PREFIX + "/" + suffix)
            member.size = len(data)
            stream.addfile(member, io.BytesIO(data))
        for name, target, kind in [*links, *extras]:
            member = tarfile.TarInfo(name)
            member.type = kind
            member.linkname = target
            stream.addfile(member)
    return path


def test_exact_two_skipped_without_creation_or_following(raw):
    path = archive(raw / "fixture.tar.gz")
    source, info = m.safe_extract(path, raw / "source")
    assert (source / "setup.py").read_bytes() == b"pass\n"
    assert info["entries"] == 4 and info["extracted_file_bytes"] == 12
    assert len(info["skipped_gallery_symlinks"]) == 2
    assert info["links_created"] == info["links_followed"] == 0
    for row in info["skipped_gallery_symlinks"]:
        assert not row["created"] and not row["followed"]
        assert not (raw / "source" / row["name"]).exists()
        assert not (raw / "source" / row["name"]).is_symlink()


@pytest.mark.parametrize(
    "kind,target",
    [
        (tarfile.LNKTYPE, "../../astronaut.jpg"),
        (tarfile.SYMTYPE, "/etc/passwd"),
        (tarfile.REGTYPE, ""),
    ],
)
def test_whitelisted_name_is_not_blanket_exemption(raw, kind, target):
    names = list(m.SKIPPED_LINKS)
    links = [(names[0], target, kind), (names[1], m.SKIPPED_LINKS[names[1]], tarfile.SYMTYPE)]
    path = archive(raw / "fixture.tar.gz", links=links)
    with pytest.raises(ValueError, match="exact_demo_symlink"):
        m.safe_extract(path, raw / "source")


@pytest.mark.parametrize(
    "name,kind",
    [
        ("vision-other/gallery/link", tarfile.SYMTYPE),
        (m.PREFIX + "/gallery/third-link", tarfile.SYMTYPE),
        (m.PREFIX + "/hardlink", tarfile.LNKTYPE),
        (m.PREFIX + "/fifo", tarfile.FIFOTYPE),
        (m.PREFIX + "/../escape", tarfile.REGTYPE),
    ],
)
def test_other_unsafe_members_still_rejected(raw, name, kind):
    path = archive(raw / "fixture.tar.gz", extras=[(name, "../elsewhere", kind)])
    with pytest.raises(
        ValueError, match="vision_build_(safe_archive_path|no_archive_links_devices)"
    ):
        m.safe_extract(path, raw / "source")


def test_missing_or_duplicate_declared_link_fails(raw):
    path = archive(raw / "missing.tar.gz", links=[])
    with pytest.raises(ValueError, match="both_declared_links_recorded"):
        m.safe_extract(path, raw / "missing")
    name, target = next(iter(m.SKIPPED_LINKS.items()))
    path = archive(raw / "duplicate.tar.gz", extras=[(name, target, tarfile.SYMTYPE)])
    with pytest.raises(ValueError, match="safe_archive_path"):
        m.safe_extract(path, raw / "duplicate")


@pytest.mark.parametrize("limit,value", [("MAX_ENTRIES", 3), ("MAX_EXTRACTED_BYTES", 1)])
def test_old_caps_remain_active(raw, monkeypatch, limit, value):
    path = archive(raw / "fixture.tar.gz")
    monkeypatch.setattr(m.old, limit, value)
    with pytest.raises(ValueError, match="vision_build_archive_.*cap"):
        m.safe_extract(path, raw / "source")


def test_helper_code_is_reused_without_old_global_mutation(raw):
    original_root = m.old.RAW
    original_create = m.old.create_environment
    ns = m.helpers()
    assert ns["RAW"] == raw and m.old.RAW == original_root
    assert ns["create_environment"].__code__ is original_create.__code__
    assert ns["create_environment"].__globals__ is ns
    assert ns["pip_install"].__globals__["RAW"] == raw
    assert m.old.create_environment is original_create
    assert all(name not in ns for name in ["acquire", "allowed_url", "NoRedirect", "run"])
    ns["BUILD_FLAGS"]["MAX_JOBS"] = "1"
    assert m.old.BUILD_FLAGS["MAX_JOBS"] == "8"


def test_cached_copy_checks_bytes_and_preserves_original(raw):
    parent = raw.parent / "old"
    parent.mkdir()
    payload = b"synthetic original cache"
    source = parent / "source.bin"
    source.write_bytes(payload)
    receipt = parent / "receipt.json"
    receipt.write_text('{"synthetic":true}')
    item = dict(
        original_file=m.old.ref(source),
        original_receipt=m.old.ref(receipt),
        artifact=dict(key="source", filename="source.bin"),
    )
    result = m.reuse({"id": "synthetic"}, item)
    assert result["network_requests"] == result["HTTP_requests"] == 0
    assert result["copied_file"]["sha256"] == hashlib.sha256(payload).hexdigest()
    assert source.read_bytes() == payload and receipt.read_text() == '{"synthetic":true}'
    assert (raw / "receipts/source.json").is_file()
    with pytest.raises(FileExistsError):
        m.reuse({"id": "synthetic"}, item)


def test_no_retry_for_reserved_new_attempt(raw, monkeypatch):
    monkeypatch.setattr(m, "protocol", lambda root: {"id": "synthetic"})
    m.base.write(raw / "attempt.json", {"reserved": True})
    monkeypatch.setattr(m, "reuse", lambda *args: pytest.fail("no cached retry"))
    with pytest.raises(ValueError, match="reserved_no_retry"):
        m.run(raw)


def test_failed_completion_reuse_does_not_fetch_or_build(raw, monkeypatch):
    monkeypatch.setattr(m, "protocol", lambda root: {"id": "synthetic"})
    result = m.base.record(
        m.COMPLETE,
        protocol_id="synthetic",
        status="CACHED_SOURCE_BUILD_FAILED_NO_AUTOMATIC_RETRY",
        network_requests=0,
        HTTP_requests=0,
    )
    m.save(raw / "summary.json", result)
    monkeypatch.setattr(m, "reuse", lambda *args: pytest.fail("no retry"))
    assert m.run(raw) == result
