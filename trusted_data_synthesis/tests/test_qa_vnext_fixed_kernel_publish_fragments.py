"""Small physical-fragment attacks; no real credential, wallet, Git, API or GPU."""

import copy
import gzip
import io
import tarfile

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import publish as pub

SECRET = b"SYNTHETIC_FRAGMENT_BOUNDARY_SECRET_0123456789"


@pytest.fixture
def small_limits(monkeypatch):
    monkeypatch.setattr(pub, "MAX_SHARD_BYTES", 32 * 1024)
    monkeypatch.setattr(pub, "FRAGMENT_BYTES", 8 * 1024)


def raw_json():
    return p.encode({"original_public_payload": "abcXYZ012345" * 6000})


def source(root, name="logical.json", raw=None):
    raw = raw_json() if raw is None else raw
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return pub._scan_member(root, name, SECRET, {})


def package(root, destination, originals):
    destination.mkdir()
    physical = pub._physical_members(root, originals, SECRET)
    groups = pub._partition(physical)
    archives = []
    for index, rows in enumerate(groups):
        name = f"shard-{index:05d}.tar.gz"
        archives.append(pub._pack(root, rows, destination / name, SECRET))
        for row in rows:
            row["publication_archive"] = name
    return physical, archives


def test_complete_logical_JSON_fragments_have_gapless_offsets_and_full_SHA(tmp_path, small_limits):
    root, destination = tmp_path / "raw", tmp_path / "sealed"
    root.mkdir()
    original = source(root)
    assert original["bytes"] > pub.MAX_SHARD_BYTES
    physical, archives = package(root, destination, [original])
    assert len(archives) > 1 and original["physical_member_count"] == len(physical) > 1
    assert [row["fragment_index"] for row in physical] == list(range(len(physical)))
    assert [row["logical_offset"] for row in physical] == list(
        range(0, original["bytes"], pub.FRAGMENT_BYTES)
    )
    assert sum(row["bytes"] for row in physical) == original["bytes"]
    assert all(row["bytes"] <= pub.FRAGMENT_BYTES for row in physical)
    assert all(
        archive["bytes"] <= pub.MAX_SHARD_BYTES
        and archive["raw_tar_bytes"] <= pub.MAX_SHARD_BYTES
        and archive["every_member_roundtrip_verified"]
        for archive in archives
    )
    pub._logical_roundtrips(root, destination, [original], physical)
    assert original["logical_reconstruction_SHA_verified"] is True
    assert p.sha((root / original["path"]).read_bytes()) == original["sha256"]


def test_identical_content_at_distinct_paths_is_never_deduplicated(tmp_path, small_limits):
    root, destination = tmp_path / "raw", tmp_path / "sealed"
    root.mkdir()
    originals = [source(root, "first/same.json"), source(root, "second/same.json")]
    assert originals[0]["sha256"] == originals[1]["sha256"]
    physical, _ = package(root, destination, originals)
    assert len({row["path"] for row in physical}) == len(physical)
    assert {row["logical_path"] for row in physical} == {row["path"] for row in originals}
    assert sum(row["bytes"] for row in physical) == sum(row["bytes"] for row in originals)
    pub._logical_roundtrips(root, destination, originals, physical)
    assert all(row["logical_reconstruction_SHA_verified"] for row in originals)


def test_valid_gzip_with_corrupted_fragment_payload_is_rejected(tmp_path, small_limits):
    root, destination = tmp_path / "raw", tmp_path / "sealed"
    root.mkdir()
    originals = [source(root)]
    physical, archives = package(root, destination, originals)
    path = destination / archives[0]["path"]
    raw = bytearray(gzip.decompress(path.read_bytes()))
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
        offset = archive.getmembers()[0].offset_data
    raw[offset + 10] ^= 1
    path.write_bytes(gzip.compress(bytes(raw), mtime=0))
    with pytest.raises(ValueError, match="exact_logical_fragment_reconstruction"):
        pub._logical_roundtrips(root, destination, originals, physical)
    assert not originals[0].get("logical_reconstruction_SHA_verified", False)


def test_reversing_physical_index_order_cannot_pass_roundtrip(tmp_path, small_limits):
    root, destination = tmp_path / "raw", tmp_path / "sealed"
    root.mkdir()
    originals = [source(root)]
    physical, _ = package(root, destination, originals)
    with pytest.raises(ValueError, match="complete_logical_physical_member_index"):
        pub._logical_roundtrips(root, destination, originals, list(reversed(physical)))


def test_missing_final_archive_cannot_pass_as_a_successful_prefix(tmp_path, small_limits):
    root, destination = tmp_path / "raw", tmp_path / "sealed"
    root.mkdir()
    originals = [source(root)]
    physical, archives = package(root, destination, originals)
    missing = archives[-1]["path"]
    prefix = [row for row in physical if row["publication_archive"] != missing]
    with pytest.raises(ValueError, match="original_full_logical_SHA_roundtrip"):
        pub._logical_roundtrips(root, destination, originals, prefix)


def test_secret_crossing_fragment_boundary_is_found_without_value_disclosure(
    tmp_path, small_limits
):
    root = tmp_path / "raw"
    root.mkdir()
    prefix = b'{"payload":"'
    padding = pub.FRAGMENT_BYTES - len(prefix) - len(SECRET) // 2
    raw = prefix + b"x" * padding + SECRET + b"z" * (pub.MAX_SHARD_BYTES * 2) + b'"}'
    assert raw == p.encode(
        {"payload": "x" * padding + SECRET.decode() + "z" * (pub.MAX_SHARD_BYTES * 2)}
    )
    assert SECRET in raw
    assert all(
        SECRET not in raw[start : start + pub.FRAGMENT_BYTES]
        for start in range(0, len(raw), pub.FRAGMENT_BYTES)
    )
    (root / "logical.json").write_bytes(raw)
    # Bypass the earlier whole-file scanner deliberately: the physical planner
    # must independently reject cross-boundary credentials before shard writing.
    original = {"path": "logical.json", "bytes": len(raw), "sha256": p.sha(raw), "format": "json"}
    with pytest.raises(ValueError, match="credential_detected_no_value_disclosed") as error:
        pub._physical_members(root, [original], SECRET)
    assert SECRET.decode() not in str(error.value)
    assert list(root.iterdir()) == [root / "logical.json"]


def test_source_change_after_fragment_planning_is_rejected_before_archiving(tmp_path, small_limits):
    root = tmp_path / "raw"
    root.mkdir()
    original = source(root)
    physical = pub._physical_members(root, [original], SECRET)
    before = (root / original["path"]).read_bytes()
    changed = bytearray(before)
    changed[100] ^= 1
    (root / original["path"]).write_bytes(changed)
    with pytest.raises(ValueError, match="source_unchanged_before_packing"):
        pub._pack(root, pub._partition(physical)[0], tmp_path / "partial.tar.gz", SECRET)


def test_fragment_that_cannot_fit_registered_shard_is_rejected_not_truncated(
    tmp_path, small_limits, monkeypatch
):
    root = tmp_path / "raw"
    root.mkdir()
    original = source(root)
    before = copy.deepcopy(original)
    monkeypatch.setattr(pub, "FRAGMENT_BYTES", pub.MAX_SHARD_BYTES)
    with pytest.raises(ValueError, match="registered_fragment_fits_shard"):
        pub._physical_members(root, [original], SECRET)
    assert original == before
    assert p.sha((root / original["path"]).read_bytes()) == original["sha256"]
