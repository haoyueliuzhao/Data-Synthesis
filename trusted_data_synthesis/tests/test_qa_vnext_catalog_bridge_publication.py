"""Transport controls, independent of production source/selection/model rules."""

import importlib.util
from pathlib import Path

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_task_build.archive import (
    record,
    sha,
    write_json,
)

SCRIPT = Path(__file__).parents[1] / "scripts/package_qa_vnext_catalog_bridge.py"
SPEC = importlib.util.spec_from_file_location("bridge_publication", SCRIPT)
publication = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publication)


def fixture(root):
    directory = root / "sealed"
    directory.mkdir()
    original = directory / "large.json"
    original.write_bytes(b'{"preserve":"raw \\r\\n bytes"}\r\n')
    write_json(
        directory / "manifest.json",
        record(
            "manifest",
            members=[
                {
                    "path": "large.json",
                    "bytes": original.stat().st_size,
                    "sha256": sha(original),
                }
            ],
        ),
    )
    return original


def test_exact_round_trip_and_existing_bytes(tmp_path):
    original = fixture(tmp_path)
    before = original.read_bytes()
    manifest_before = (original.parent / "manifest.json").read_bytes()
    publication.pack(tmp_path, artifact="sealed", threshold=10)
    first = publication.restore(tmp_path, artifact="sealed")
    assert first["already_exact"] == ["large.json"] and first["restored"] == []
    original.unlink()  # Test-only temporary fixture, not a production artifact.
    second = publication.restore(tmp_path, artifact="sealed")
    assert second["restored"] == ["large.json"]
    assert original.read_bytes() == before
    assert (original.parent / "manifest.json").read_bytes() == manifest_before


def test_never_overwrite_existing_mismatch(tmp_path):
    original = fixture(tmp_path)
    publication.pack(tmp_path, artifact="sealed", threshold=10)
    original.write_bytes(b"user changed this")
    with pytest.raises(ValueError, match="never_overwrite"):
        publication.restore(tmp_path, artifact="sealed")
    assert original.read_bytes() == b"user changed this"


def test_compressed_corruption_rejected(tmp_path):
    fixture(tmp_path)
    index = publication.pack(tmp_path, artifact="sealed", threshold=10)
    compressed = tmp_path / "sealed_publication" / index["members"][0]["gzip_path"]
    compressed.write_bytes(b"not the registered bytes")
    with pytest.raises(ValueError, match="compressed_identity"):
        publication.restore(tmp_path, artifact="sealed")


def test_manifest_change_rejected(tmp_path):
    original = fixture(tmp_path)
    publication.pack(tmp_path, artifact="sealed", threshold=10)
    manifest = original.parent / "manifest.json"
    manifest.unlink()
    write_json(manifest, record("manifest", members=[]))
    with pytest.raises(ValueError, match="original_manifest_join"):
        publication.restore(tmp_path, artifact="sealed")


def test_symlink_member_rejected(tmp_path):
    original = fixture(tmp_path)
    publication.pack(tmp_path, artifact="sealed", threshold=10)
    outside = tmp_path / "user_file"
    outside.write_bytes(original.read_bytes())
    original.unlink()
    original.symlink_to(outside)
    with pytest.raises(ValueError, match="symlink"):
        publication.restore(tmp_path, artifact="sealed")


def test_pack_is_single_transport_creation(tmp_path):
    fixture(tmp_path)
    publication.pack(tmp_path, artifact="sealed", threshold=10)
    with pytest.raises(ValueError, match="new_transport_directory"):
        publication.pack(tmp_path, artifact="sealed", threshold=10)
