"""Audit identity for a new read-only verification/supervisor implementation."""

import hashlib
import json
import os
from pathlib import Path

BASE_COMMIT = "fcb0607b81709479285e30f4e42a8e9f53094647"
BRANCH = "codex/linear-postprocess-20260913"
PACKAGE = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_linear_postprocess"
)
OPERATION = "trusted_data_synthesis/artifacts/qa_vnext_linear_postprocess/handoff_20260913"
OLD_FOLLOW_PID = 726630
OLD_COLLECTION_PID = 644313


def require(value, message):
    if not value:
        raise ValueError(message)


def encode(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def sha(value):
    if isinstance(value, Path):
        with value.open("rb") as handle:
            return hashlib.file_digest(handle, "sha256").hexdigest()
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def record(kind, **fields):
    body = {"schema_version": "linear_postprocess.v1." + kind, **fields}
    return {**body, "id": kind + ":" + sha(encode(body))}


def checked(value, kind):
    require(
        value
        == record(
            kind,
            **{key: item for key, item in value.items() if key not in {"id", "schema_version"}},
        ),
        "linear.content_addressed_record",
    )
    return value


def write_once(path, value):
    path = Path(path)
    require(
        not any(part.is_symlink() for part in (path, *path.parents)), "linear.no_symlink_output"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(encode(value))
        stream.flush()
        os.fsync(stream.fileno())
    return value


def policy():
    return record(
        "linear_verification_policy",
        version="pinned_POSIX_manifest_snapshot.v1",
        base_commit=BASE_COMMIT,
        changed_historical_source_files=0,
        manifest="fixed O_NOFOLLOW descriptor; exact SHA at entry and final verification boundary",
        each_read=(
            "same manifest fd and namespace inode/ctime/mtime/size/mode/link-count; "
            "actual member SHA and size"
        ),
        paths=(
            "directory-fd traversal with O_DIRECTORY|O_NOFOLLOW; reject symlinks and special files"
        ),
        full_set=(
            "exact declared files and only their required directories; before and after full sweep"
        ),
        late_mutation="final file and directory stat sweep compared with initial pinned metadata",
        same_timestamp_tick_defense=(
            "Linux inotify watches pinned manifest/member inodes and directories"
        ),
        notification_failure=(
            "any mutation, unexpected lost watch, queue overflow or unavailable watch fails closed"
        ),
        notifications_shared_within_supervisor=True,
        watch_lifecycle=(
            "per-owner reference counts; only successful removal's exact pure IN_IGNORED "
            "is cleanup; real or mixed events remain fatal"
        ),
        member_content_cache=False,
        manifest_member_loop_full_rehash=False,
        static_valid_declared_inputs=(
            "same original Parent bytes/read/descriptor/verify_all result identities"
        ),
        acceptance_domain=(
            "stricter: undeclared files/empty directories and namespace/stat changes rejected"
        ),
        assumption=(
            "sealed local Linux filesystem with no writer; not an atomic filesystem snapshot, "
            "and not protection against preexisting writable mmap, direct storage "
            "or privileged kernel mutation"
        ),
        financial_parser_or_assessment_modified=False,
        package_selection_modified=False,
        budget_or_Teacher_protocol_modified=False,
        training_decoder_or_analysis_rule_modified=False,
        new_collection_requests=0,
        original_collect_restarted=False,
        handoff="only after old collector and old read-only supervisor are confirmed stopped",
        abandoned_work=(
            "repeated read-only hashes; no original collection/material records discarded"
        ),
        production_handoff_requires_explicit_review=True,
        this_policy_record_alone_authorizes_execution=False,
    )
