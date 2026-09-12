"""Lossless transport for oversized sealed members; never rewrite scientific artifacts."""

import argparse
import gzip
import hashlib
import os
import shutil
import tempfile
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge.catalog import (
    Parent,
    read,
    safe_path,
)
from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge.protocol import OUTPUT
from trusted_synthesis.experiments.finance_qa_vnext_task_build.archive import (
    record,
    require,
    sha,
    validate_record,
    write_json,
)

GIT_LIMIT = 100 * 1024 * 1024
CHUNK = 1024 * 1024


def inflate(compressed, member, sink=None):
    digest, count = hashlib.sha256(), 0
    with gzip.open(compressed, "rb") as source:
        while block := source.read(CHUNK):
            count += len(block)
            require(count <= member["bytes"], "publication.inflation_bound")
            digest.update(block)
            if sink is not None:
                sink.write(block)
    require(
        count == member["bytes"] and digest.hexdigest() == member["sha256"],
        "publication.exact_original_bytes",
    )


def pack(root, *, artifact=OUTPUT, threshold=GIT_LIMIT):
    root = Path(root).resolve()
    parent = Parent(root, artifact)
    require(type(threshold) is int and threshold > 0, "publication.positive_threshold")
    directory = safe_path(root, artifact + "_publication")
    require(not directory.exists(), "publication.new_transport_directory")
    parent.verify_all()
    directory.mkdir(parents=True)
    members = []
    for relative, member in sorted(parent.members.items()):
        if member["bytes"] <= threshold:
            continue
        original = safe_path(parent.directory, relative)
        filename = member["sha256"] + ".json.gz"
        destination = directory / filename
        with original.open("rb") as source, destination.open("xb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
                shutil.copyfileobj(source, compressed, CHUNK)
        inflate(destination, member)
        require(destination.stat().st_size <= GIT_LIMIT, "publication.compressed_Git_size")
        members.append(
            {
                "original": member,
                "gzip_path": filename,
                "gzip_bytes": destination.stat().st_size,
                "gzip_sha256": sha(destination),
            }
        )
    index = record(
        "lossless_publication",
        artifact=artifact,
        parent=parent.descriptor(),
        member_byte_threshold=threshold,
        members=members,
        scientific_manifest_replaced=False,
        original_files_deleted_or_modified=False,
        purpose="byte transport only; decompress before normal manifest verification",
    )
    write_json(directory / "index.json", index)
    return index


def restore(root, *, artifact=OUTPUT):
    root = Path(root).resolve()
    parent = Parent(root, artifact)
    directory = safe_path(root, artifact + "_publication")
    index = read(safe_path(directory, "index.json"))
    validate_record(index, "lossless_publication")
    require(index["parent"] == parent.descriptor(), "publication.original_manifest_join")
    require(index["artifact"] == artifact, "publication.exact_artifact")
    threshold = index["member_byte_threshold"]
    require(type(threshold) is int and threshold > 0, "publication.positive_threshold")
    expected = {path for path, member in parent.members.items() if member["bytes"] > threshold}
    actual = [row["original"]["path"] for row in index["members"]]
    require(set(actual) == expected and len(actual) == len(expected), "publication.exact_members")
    restored, unchanged = [], []
    for row in index["members"]:
        member = row["original"]
        require(member == parent.members[member["path"]], "publication.member_manifest_join")
        compressed = safe_path(directory, row["gzip_path"])
        require(
            compressed.stat().st_size == row["gzip_bytes"]
            and sha(compressed) == row["gzip_sha256"],
            "publication.compressed_identity",
        )
        target = safe_path(parent.directory, member["path"])
        if target.exists():
            require(
                target.stat().st_size == member["bytes"] and sha(target) == member["sha256"],
                "publication.never_overwrite_existing_mismatch",
            )
            inflate(compressed, member)
            unchanged.append(member["path"])
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as sink:
                temporary = Path(sink.name)
                inflate(compressed, member, sink)
                sink.flush()
                os.fsync(sink.fileno())
            # Atomic exclusive creation: never replace an existing file in a race.
            os.link(temporary, target)
            restored.append(member["path"])
        finally:
            if temporary is not None:
                temporary.unlink()
    parent.verify_all()
    return {
        "manifest_id": parent.manifest["id"],
        "restored": restored,
        "already_exact": unchanged,
        "all_members_verified": len(parent.members),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("pack", "restore"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    result = {"pack": pack, "restore": restore}[args.phase](args.root)
    print({"phase": args.phase, "result": result})


if __name__ == "__main__":
    main()
