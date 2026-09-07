"""Immutable published history binding; no old qualification, comparison or Token replay."""

import hashlib
import subprocess
from pathlib import Path

from ..finance_qa_vnext_model_execution.models import record, require, sha

PARENT_COMMIT = "1df42747bedfce1ef874fb2a2f3fb7566513964a"

HISTORY_PREFIXES = (
    "qa_vnext_integration",
    "qa_vnext_model_execution",
    "qa_vnext_update_calibration",
    "qa_vnext_repaired_full_task",
    "qa_vnext_action_branch",
    "qa_vnext_length_adaptation",
    "qa_vnext_task_panel",
    "qa_vnext_panel_quotient",
    "qa_vnext_support_exploration",
    "qa_vnext_support_transition",
)


def _members(root, prefixes, *, python_only=False):
    tree = subprocess.check_output(
        ["git", "ls-tree", "-r", "-z", PARENT_COMMIT, "--", *prefixes], cwd=root
    )
    rows = []
    for item in tree.split(b"\0"):
        if not item:
            continue
        metadata, name = item.split(b"\t", 1)
        mode, kind, oid = metadata.decode().split()
        path = root / name.decode()
        if python_only and path.suffix != ".py":
            continue
        require(
            mode == "100644" and kind == "blob" and path.is_file() and not path.is_symlink(),
            "cross_binding.published_file",
        )
        raw = path.read_bytes()
        require(
            hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == oid,
            "cross_binding.historical_bytes_changed",
        )
        rows.append(
            {"path": name.decode(), "bytes": len(raw), "sha256": sha(raw), "git_blob_id": oid}
        )
    return rows


def history_inventory(root: Path):
    prefixes = ["trusted_data_synthesis/artifacts/" + name for name in HISTORY_PREFIXES]
    members = _members(root, prefixes)
    actual = set()
    for prefix in prefixes:
        for path in (root / prefix).rglob("*"):
            require(not path.is_symlink(), "cross_binding.historical_symlink")
            if path.is_file():
                actual.add(path.relative_to(root).as_posix())
    require(actual == {item["path"] for item in members}, "cross_binding.historical_member_set")
    require(
        len(members) == 15_908 and sum(m["bytes"] for m in members) == 805_563_921,
        "cross_binding.historical_population",
    )
    return record(
        "cross_binding_history_inventory",
        predecessor_commit=PARENT_COMMIT,
        members=members,
        file_count=len(members),
        byte_count=sum(m["bytes"] for m in members),
        all_bytes_match_published_git_blobs=True,
        old_populations_unchanged=True,
    )


def preserved_sources(root: Path):
    members = _members(root, ["trusted_data_synthesis/src"], python_only=True)
    require(len(members) == 918, "cross_binding.predecessor_source_count")
    return record(
        "cross_binding_source_preservation",
        predecessor_commit=PARENT_COMMIT,
        members=members,
        file_count=len(members),
        all_predecessor_python_bytes_unchanged=True,
        old_runtime_qualification_quotient_representation_modified=False,
    )
