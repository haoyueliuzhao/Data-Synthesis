"""Publish only exact, closed scientific outputs under an advisory Git lock.

No call rewrites or compresses scientific files. Failures intentionally leave
local commits/staging intact for inspection; the supervising follow process
persists its failure outside these sealed output directories.
"""

import fcntl
import hashlib
import os
import shlex
import subprocess
from contextlib import contextmanager
from pathlib import Path

from ..finance_qa_vnext_catalog_bridge.catalog import Parent
from . import protocol as p

REMOTE = "https://github.com/haoyueliuzhao/Data-Synthesis.git"
BRANCH = "main"
MAX_FILE_BYTES = 100 * 1024 * 1024
LOCK_PATH = "trusted_data_synthesis/runtime/basis_student_publication.lock"


def _require(condition, code):
    p.require(condition, "publication." + code)


def _git(root, *arguments, input_bytes=None, allowed_failure=False):
    # Environment-supplied alternate indices/configs must not redirect this job.
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment["GIT_TERMINAL_PROMPT"] = "0"
    result = subprocess.run(
        ["git", "-c", "core.autocrlf=false", "--literal-pathspecs", *arguments],
        cwd=root,
        env=environment,
        input=input_bytes,
        capture_output=True,
        check=False,
    )
    if not allowed_failure:
        _require(result.returncode == 0, f"git_{arguments[0]}_failed_exit_{result.returncode}")
    return result


def _text(root, *arguments):
    return _git(root, *arguments).stdout.decode("utf-8").strip()


def _names(raw):
    return [part.decode("utf-8") for part in raw.split(b"\0") if part]


def _inside(name, directories):
    return any(name.startswith(directory + "/") for directory in directories)


def _unchanged_main(root, expected_head=None):
    _require(_text(root, "symbolic-ref", "--short", "HEAD") == BRANCH, "main_branch_required")
    head = _text(root, "rev-parse", "HEAD")
    _require(expected_head is None or head == expected_head, "concurrent_HEAD_change")
    return head


@contextmanager
def _lock(root):
    path = root / LOCK_PATH
    _require(not any(item.is_symlink() for item in (path, *path.parents)), "runtime_lock_symlink")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("publication.concurrent_publisher") from error
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _credential(root):
    path = root / "trusted_data_synthesis/.env"
    _require(path.is_file() and not path.is_symlink(), "credential_scan_source_required")
    values = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        if separator and key.strip() == "DEEPSEEK_API_KEY":
            parsed = shlex.split(value, comments=True)
            _require(len(parsed) == 1 and len(parsed[0]) >= 8, "credential_scan_value_required")
            values.append(parsed[0].encode("utf-8"))
    _require(len(values) == 1, "one_credential_scan_value_required")
    return values[0]


def _file(root, path, secret, object_format):
    relative = path.relative_to(root).as_posix()
    lower = path.name.lower()
    _require(not any(ord(char) < 32 for char in relative), "control_character_path")
    _require(
        not (
            lower == ".env"
            or lower.startswith(".env.")
            or lower.endswith(".env")
            or any(marker in lower for marker in (".sqlite", ".sqlite3"))
            or lower.endswith((".db", ".db-wal", ".db-shm", ".pem", ".key"))
            or lower in {"id_rsa", "id_ed25519", "credentials"}
        ),
        "forbidden_database_environment_or_private_key_file",
    )
    size = path.stat().st_size
    _require(size < MAX_FILE_BYTES, "file_at_least_100_MiB_blocked_no_rewrite")
    raw_sha = hashlib.sha256()
    git_blob = hashlib.new(object_format)
    git_blob.update(f"blob {size}\0".encode())
    matched, tail, first, observed = 0, b"", True, 0
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            if first:
                _require(not chunk.startswith(b"SQLite format 3\0"), "SQLite_content_forbidden")
                first = False
            raw_sha.update(chunk)
            git_blob.update(chunk)
            observed += len(chunk)
            combined = tail + chunk
            matched += combined.count(secret)
            tail = combined[-(len(secret) - 1) :]
    _require(observed == size == path.stat().st_size, "file_changed_while_hashing")
    return {
        "path": relative,
        "bytes": size,
        "sha256": raw_sha.hexdigest(),
        "git_blob": git_blob.hexdigest(),
    }, matched


def _snapshot(root, directories, secret, object_format):
    files, parents, matched = {}, [], 0
    for directory in directories:
        folder = root / directory
        _require(
            folder.is_dir() and not any(item.is_symlink() for item in (folder, *folder.parents)),
            "closed_regular_output_directory",
        )
        parent = Parent(root, directory)
        parent.verify_all()
        declared = {row["path"] for row in parent.manifest["members"]}
        _require(len(declared) == len(parent.manifest["members"]), "unique_manifest_members")
        actual = []
        for path in folder.rglob("*"):
            _require(
                not path.is_symlink() and path.name != ".git", "symlink_or_nested_git_forbidden"
            )
            _require(path.is_dir() or path.is_file(), "only_regular_files_and_directories")
            if path.is_file():
                actual.append(path)
        _require(
            {path.relative_to(folder).as_posix() for path in actual}
            == declared | {"manifest.json"},
            "exact_closed_manifest_no_extra_private_files",
        )
        for path in sorted(actual):
            descriptor, count = _file(root, path, secret, object_format)
            files[descriptor["path"]] = descriptor
            matched += count
        parents.append(
            {
                "directory": directory,
                "manifest_id": parent.manifest["id"],
                "manifest_sha256": files[directory + "/manifest.json"]["sha256"],
            }
        )
    return files, parents, matched


def _no_filters(root, files):
    raw = _git(
        root,
        "check-attr",
        "-z",
        "--stdin",
        "filter",
        input_bytes=b"\0".join(name.encode() for name in files) + b"\0",
    ).stdout
    parts = _names(raw)
    _require(len(parts) == 3 * len(files), "complete_Git_filter_attributes")
    for index in range(0, len(parts), 3):
        name, attribute, value = parts[index : index + 3]
        _require(
            name in files and attribute == "filter" and value in {"unspecified", "unset"},
            "active_Git_clean_filter_blocked",
        )


def _verify_index(root, directories, files):
    raw = _git(root, "ls-files", "--stage", "-z", "--", *directories).stdout
    found = {}
    for item in raw.split(b"\0"):
        if not item:
            continue
        prefix, name = item.split(b"\t", 1)
        mode, blob, stage = prefix.decode().split()
        name = name.decode("utf-8")
        _require(
            mode in {"100644", "100755"} and stage == "0" and name in files,
            "ordinary_stage_zero_allowlist_only",
        )
        _require(blob == files[name]["git_blob"], "index_blob_not_original_raw_bytes")
        found[name] = blob
    _require(set(found) == set(files), "complete_original_file_index")


def _verify_tree(root, commit, directories, files):
    raw = _git(root, "ls-tree", "-r", "-z", commit, "--", *directories).stdout
    found = {}
    for item in raw.split(b"\0"):
        if not item:
            continue
        prefix, name = item.split(b"\t", 1)
        mode, kind, blob = prefix.decode().split()
        name = name.decode("utf-8")
        _require(
            mode in {"100644", "100755"} and kind == "blob" and name in files,
            "committed_tree_file_allowlist",
        )
        _require(blob == files[name]["git_blob"], "committed_blob_not_original_raw_bytes")
        found[name] = blob
    _require(set(found) == set(files), "complete_original_committed_tree")


def _remote_head(root):
    lines = _text(root, "ls-remote", "--exit-code", REMOTE, "refs/heads/main").splitlines()
    _require(len(lines) == 1 and lines[0].split()[1:] == ["refs/heads/main"], "one_remote_main")
    value = lines[0].split()[0]
    _require(
        len(value) in {40, 64} and all(char in "0123456789abcdef" for char in value),
        "remote_commit_identity",
    )
    return value


def publish(root, relative_directories, *, message):
    """Commit and verify explicit-main publication of closed outputs, or fail closed."""
    root = Path(root).absolute()
    _require(root == root.resolve(), "non_symlink_repository_root")
    _require(
        isinstance(relative_directories, (list, tuple)) and relative_directories,
        "explicit_nonempty_output_scopes",
    )
    allowed = {p.COLLECTION, p.MATERIALS, p.OUTPUT}
    _require(
        all(isinstance(item, str) and item in allowed for item in relative_directories)
        and len(set(relative_directories)) == len(relative_directories),
        "exact_registered_scopes_only",
    )
    directories = sorted(relative_directories)
    _require(isinstance(message, str) and bool(message.strip()), "explicit_result_commit_message")
    _require(
        Path(_text(root, "rev-parse", "--show-toplevel")).resolve() == root,
        "exact_Git_worktree_root",
    )
    with _lock(root):
        starting_head = _unchanged_main(root)
        _require(
            not _git(root, "diff", "--cached", "--name-only", "-z").stdout,
            "preexisting_staged_changes_not_owned",
        )
        object_format = _text(root, "rev-parse", "--show-object-format")
        _require(object_format in {"sha1", "sha256"}, "supported_raw_Git_object_format")
        secret = _credential(root)
        files, parents, matches = _snapshot(root, directories, secret, object_format)
        matches += message.encode().count(secret)
        _require(matches == 0, f"credential_match_count={matches}")
        _no_filters(root, files)
        _git(root, "add", "-f", "--", *directories)
        staged = _names(_git(root, "diff", "--cached", "--name-only", "-z").stdout)
        _require(
            all(_inside(name, directories) for name in staged), "staged_paths_outside_owned_scope"
        )
        _verify_index(root, directories, files)
        current_files, current_parents, matches = _snapshot(
            root, directories, secret, object_format
        )
        _require(
            current_files == files and current_parents == parents and matches == 0,
            "sealed_files_changed_before_commit",
        )
        _unchanged_main(root, starting_head)
        if staged:
            _git(root, "commit", "-q", "-m", message)
        commit = _unchanged_main(root)
        if staged:
            _require(
                _text(root, "rev-parse", commit + "^") == starting_head,
                "commit_parent_changed_concurrently",
            )
            changed = _names(_git(root, "diff", "--name-only", "-z", starting_head, commit).stdout)
            _require(
                all(_inside(name, directories) for name in changed),
                "committed_change_outside_owned_scope",
            )
        else:
            _require(commit == starting_head, "no_change_must_not_create_commit")
        _verify_tree(root, commit, directories, files)
        _require(
            not _git(root, "diff", "--cached", "--name-only", "-z").stdout,
            "concurrent_staging_after_commit",
        )
        remote_before = _remote_head(root)
        _require(
            _git(
                root, "merge-base", "--is-ancestor", remote_before, commit, allowed_failure=True
            ).returncode
            == 0,
            "remote_main_not_local_ancestor_no_force",
        )
        pending = _names(_git(root, "diff", "--name-only", "-z", remote_before, commit).stdout)
        _require(
            all(_inside(name, directories) for name in pending),
            "unpublished_changes_outside_owned_scope",
        )
        _unchanged_main(root, commit)
        if remote_before != commit:
            _git(root, "push", "--porcelain", REMOTE, commit + ":refs/heads/main")
        remote_after = _remote_head(root)
        _require(remote_after == commit, "remote_main_not_verified_published_commit")
        _unchanged_main(root, commit)
        return p.record(
            "publication_report",
            status="PUBLISHED_VERIFIED" if staged else "NO_CHANGES_REMOTE_VERIFIED",
            directories=directories,
            sealed_parents=parents,
            commit_id=commit,
            remote=REMOTE,
            branch=BRANCH,
            remote_commit_id=remote_after,
            starting_commit_id=starting_head,
            remote_previous_commit_id=remote_before,
            new_commit_created=bool(staged),
            staged_file_count=len(staged),
            published_file_count=len(files),
            credential_match_count=0,
            verified_raw_git_blobs=True,
            forced_push=False,
            scientific_files_rewritten=False,
            external_staged_changes_committed=False,
            lock_file_retained=LOCK_PATH,
        )
