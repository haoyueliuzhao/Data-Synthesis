"""Immutable published history binding; no old qualification, comparison or Token replay."""

import ast
import hashlib
import subprocess
from pathlib import Path

from ..finance_qa_vnext_model_execution.models import record, require, sha

PARENT_COMMIT = "7a750ad92dd91601461161b53ab686c6bf3eeff8"

EDITED_SOURCE_PATHS = {
    "trusted_data_synthesis/src/trusted_synthesis/domains/finance/qa_vnext/" + name
    for name in ("runtime.py", "measurement.py", "action_public_contract.py")
}
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
    "qa_vnext_cross_binding",
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
            "final_publication_preservation.published_file",
        )
        raw = path.read_bytes()
        changed = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() != oid
        if python_only and name.decode() in EDITED_SOURCE_PATHS:
            original = subprocess.check_output(
                ["git", "show", PARENT_COMMIT + ":" + name.decode()], cwd=root
            )
            rows.append(
                {
                    "path": name.decode(),
                    "bytes": len(raw),
                    "sha256": sha(raw),
                    "git_blob_id": oid,
                    "original_bytes": len(original),
                    "original_sha256": sha(original),
                    "publication_edit": changed,
                }
            )
        else:
            require(not changed, "final_publication_preservation.historical_bytes_changed")
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
            require(not path.is_symlink(), "final_publication_preservation.historical_symlink")
            if path.is_file():
                actual.add(path.relative_to(root).as_posix())
    require(
        actual == {item["path"] for item in members},
        "final_publication_preservation.historical_member_set",
    )
    require(
        len(members) == 21_269 and sum(m["bytes"] for m in members) == 980_870_310,
        "final_publication_preservation.historical_population",
    )
    return record(
        "final_publication_history_inventory",
        predecessor_commit=PARENT_COMMIT,
        members=members,
        file_count=len(members),
        byte_count=sum(m["bytes"] for m in members),
        all_bytes_match_published_git_blobs=True,
        old_populations_unchanged=True,
    )


def preserved_sources(root: Path):
    members = _members(root, ["trusted_data_synthesis/src"], python_only=True)
    require(len(members) == 932, "final_publication_preservation.predecessor_source_count")
    return record(
        "final_publication_source_preservation",
        predecessor_commit=PARENT_COMMIT,
        members=members,
        file_count=len(members),
        explicitly_changed_publication_paths=sorted(EDITED_SOURCE_PATHS),
        changed_python_count=sum(item.get("publication_edit", False) for item in members),
        all_other_predecessor_python_bytes_unchanged=True,
        original_strict_semantic_bodies_unchanged=_semantic_bodies(root),
        old_qualification_quotient_representation_source_unchanged=True,
        runtime_request_and_final_feedback_publication_changed=True,
    )


def _semantic_bodies(root: Path):
    """Compare source slices, not executions: the gates and numeric verifier stay identical."""
    checks = []
    specs = (
        ("runtime.py", ("PublicQARuntime", "_admit")),
        ("measurement.py", ("_admission",)),
        ("action_public_contract.py", ("public_action_contract",)),
        ("action_public_contract.py", ("publish_action_contract",)),
        ("bound_share_adapter.py", ("BoundShareTaskAdapter", "verify_final")),
        ("bound_share_adapter.py", ("BoundShareTaskAdapter", "verify_execution")),
        ("protocol.py", ("parse",)),
        ("share_adapter.py", ("public_share_answer",)),
    )

    def select(raw, route):
        body = ast.parse(raw.decode()).body
        node = None
        for name in route:
            node = next(item for item in body if getattr(item, "name", None) == name)
            body = node.body
        assert node is not None
        segment = ast.get_source_segment(raw.decode(), node)
        assert segment is not None
        return segment.encode()

    for filename, route in specs:
        relative = (
            "trusted_data_synthesis/src/trusted_synthesis/domains/finance/qa_vnext/" + filename
        )
        old = subprocess.check_output(["git", "show", PARENT_COMMIT + ":" + relative], cwd=root)
        new = (root / relative).read_bytes()
        original_body, current_body = select(old, route), select(new, route)
        require(
            original_body == current_body, "final_publication_preservation.strict_logic_changed"
        )
        checks.append(
            {
                "path": relative,
                "symbol": ".".join(route),
                "sha256": sha(current_body),
                "unchanged": True,
            }
        )
    return checks
