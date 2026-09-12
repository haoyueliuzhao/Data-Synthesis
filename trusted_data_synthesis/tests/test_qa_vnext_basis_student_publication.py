"""Local temporary Git repositories; push and ls-remote are always mocked."""

import fcntl
import hashlib
import json
import subprocess

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_basis_student import protocol as p
from trusted_synthesis.experiments.finance_qa_vnext_basis_student import publication as pub
from trusted_synthesis.experiments.finance_qa_vnext_task_build.archive import record

KEY = "synthetic-not-a-real-DeepSeek-secret-73409271"


def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root).decode().strip()


def seal(root, directory):
    folder = root / directory
    members = [
        {
            "path": str(path.relative_to(folder)),
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in sorted(folder.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    ]
    value = record("manifest", members=members, scope="synthetic closed outputs")
    (folder / "manifest.json").write_text(json.dumps(value), encoding="utf-8")
    return value


def repository(tmp_path, monkeypatch, directories=None):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.name", "Synthetic Controls")
    git(root, "config", "user.email", "synthetic@example.invalid")
    (root / ".gitignore").write_text(
        ".env\ntrusted_data_synthesis/artifacts/\ntrusted_data_synthesis/runtime/\n"
    )
    (root / "README.md").write_text("Initial synthetic repository.\n")
    git(root, "add", ".gitignore", "README.md")
    git(root, "commit", "-q", "-m", "synthetic base")
    (root / "trusted_data_synthesis").mkdir()
    (root / "trusted_data_synthesis/.env").write_text("export DEEPSEEK_API_KEY='" + KEY + "'\n")
    directories = directories or [p.COLLECTION, p.MATERIALS, p.OUTPUT]
    for directory in directories:
        folder = root / directory
        folder.mkdir(parents=True)
        (folder / "report.txt").write_bytes(b"Synthetic terminal result.\r\nNot an experiment.\r\n")
        seal(root, directory)
    state = {
        "remote": git(root, "rev-parse", "HEAD"),
        "pushes": [],
        "ls_remote": 0,
        "fail_push": False,
        "before_commit": None,
        "after_add": None,
    }
    real_run = subprocess.run

    def run(command, **kwargs):
        assert "core.hooksPath=/dev/null" not in command
        if "ls-remote" in command:
            state["ls_remote"] += 1
            assert pub.REMOTE in command and "refs/heads/main" in command
            return subprocess.CompletedProcess(
                command, 0, (state["remote"] + "\trefs/heads/main\n").encode(), b""
            )
        if "push" in command:
            assert pub.REMOTE in command and "--force" not in command
            refspec = command[-1]
            assert refspec.endswith(":refs/heads/main")
            state["pushes"].append(command)
            if state["fail_push"]:
                return subprocess.CompletedProcess(command, 1, b"", KEY.encode())
            state["remote"] = refspec.split(":")[0]
            return subprocess.CompletedProcess(command, 0, b"synthetic push accepted\n", b"")
        if "commit" in command and state["before_commit"]:
            callback, state["before_commit"] = state["before_commit"], None
            callback()
        result = real_run(command, **kwargs)
        if "add" in command and "-f" in command and state["after_add"]:
            callback, state["after_add"] = state["after_add"], None
            callback()
        return result

    monkeypatch.setattr(pub.subprocess, "run", run)
    return root, directories, state


def test_exact_closed_outputs_forced_from_ignore_raw_bytes_and_explicit_remote(
    tmp_path, monkeypatch
):
    root, directories, state = repository(tmp_path, monkeypatch)
    start = git(root, "rev-parse", "HEAD")
    git(root, "config", "core.autocrlf", "true")
    result = pub.publish(
        root, directories, message="Publish synthetic complete result counts and limitations"
    )
    assert result["status"] == "PUBLISHED_VERIFIED" and result["new_commit_created"]
    assert result["commit_id"] == result["remote_commit_id"] == git(root, "rev-parse", "HEAD")
    assert result["commit_id"] != start and len(state["pushes"]) == 1
    assert result["credential_match_count"] == 0 and result["verified_raw_git_blobs"]
    assert KEY not in json.dumps(result)
    for directory in directories:
        raw = subprocess.check_output(
            ["git", "show", "HEAD:" + directory + "/report.txt"], cwd=root
        )
        assert raw == (root / directory / "report.txt").read_bytes()
    changes = git(root, "diff", "--name-only", start, "HEAD").splitlines()
    assert all(
        any(path.startswith(directory + "/") for directory in directories) for path in changes
    )
    assert (root / pub.LOCK_PATH).is_file()
    assert not git(root, "diff", "--cached", "--name-only")


def test_no_changes_is_idempotent_with_remote_HEAD_reverification(tmp_path, monkeypatch):
    root, directories, state = repository(tmp_path, monkeypatch)
    first = pub.publish(root, directories, message="Synthetic closed outputs")
    second = pub.publish(root, directories, message="Must not create a duplicate commit")
    assert second["status"] == "NO_CHANGES_REMOTE_VERIFIED"
    assert not second["new_commit_created"] and second["staged_file_count"] == 0
    assert first["commit_id"] == second["commit_id"] and len(state["pushes"]) == 1
    assert state["ls_remote"] == 4


def test_preexisting_staging_is_preserved_and_not_committed(tmp_path, monkeypatch):
    root, directories, state = repository(tmp_path, monkeypatch)
    (root / "unrelated.txt").write_text("User-owned change")
    git(root, "add", "unrelated.txt")
    start = git(root, "rev-parse", "HEAD")
    with pytest.raises(ValueError, match="preexisting_staged"):
        pub.publish(root, directories, message="Synthetic")
    assert git(root, "diff", "--cached", "--name-only") == "unrelated.txt"
    assert git(root, "rev-parse", "HEAD") == start and not state["pushes"]


def test_non_main_branch_is_rejected(tmp_path, monkeypatch):
    root, directories, state = repository(tmp_path, monkeypatch)
    git(root, "checkout", "-q", "-b", "unrelated-feature")
    with pytest.raises(ValueError, match="main_branch_required"):
        pub.publish(root, directories, message="Synthetic")
    assert not state["pushes"]


@pytest.mark.parametrize(
    "scope",
    [
        [],
        [".env"],
        ["trusted_data_synthesis/artifacts"],
        [p.COLLECTION + "/sessions"],
        [p.OUTPUT, p.OUTPUT],
    ],
)
def test_only_three_exact_registered_directories_are_accepted(tmp_path, monkeypatch, scope):
    root, _, state = repository(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        pub.publish(root, scope, message="Synthetic")
    assert not state["pushes"]


@pytest.mark.parametrize("defect", ["unsealed", "extra", "changed", "symlink", "nested_git"])
def test_unclosed_or_changed_file_set_is_not_published(tmp_path, monkeypatch, defect):
    root, directories, state = repository(tmp_path, monkeypatch)
    folder = root / directories[0]
    if defect == "unsealed":
        (folder / "manifest.json").unlink()
    elif defect == "extra":
        (folder / "unlisted-private.txt").write_text("not in manifest")
    elif defect == "changed":
        (folder / "report.txt").write_text("changed after sealing")
    elif defect == "symlink":
        (folder / "linked").symlink_to(root / "trusted_data_synthesis/.env")
    elif defect == "nested_git":
        (folder / ".git").mkdir()
    with pytest.raises((ValueError, RuntimeError, FileNotFoundError)):
        pub.publish(root, directories, message="Synthetic")
    assert not git(root, "diff", "--cached", "--name-only") and not state["pushes"]


@pytest.mark.parametrize(
    "name,content",
    [
        ("wallet.sqlite3", b"x"),
        ("database.bin", b"SQLite format 3\0"),
        (".env.old", b"old=value"),
        ("settings.env", b"a=b"),
        ("id_rsa", b"synthetic"),
    ],
)
def test_database_environment_and_private_key_files_remain_unpublished(
    tmp_path, monkeypatch, name, content
):
    root, directories, state = repository(tmp_path, monkeypatch)
    folder = root / directories[0]
    (folder / name).write_bytes(content)
    seal(root, directories[0])
    with pytest.raises(ValueError, match="forbidden"):
        pub.publish(root, directories, message="Synthetic")
    assert (folder / name).read_bytes() == content and not state["pushes"]


@pytest.mark.parametrize("where", ["file", "commit_message"])
def test_actual_env_key_scan_reports_count_without_secret_or_rewriting(
    tmp_path, monkeypatch, where
):
    root, directories, state = repository(tmp_path, monkeypatch)
    message = "Synthetic"
    if where == "file":
        (root / directories[0] / "report.txt").write_text(KEY + " " + KEY)
        seal(root, directories[0])
    else:
        message += KEY
    with pytest.raises(ValueError, match="credential_match_count") as raised:
        pub.publish(root, directories, message=message)
    assert KEY not in str(raised.value)
    assert ("=2" if where == "file" else "=1") in str(raised.value)
    assert not state["pushes"]


def test_at_least_100MiB_is_publication_blocker_not_automatic_compression(tmp_path, monkeypatch):
    root, directories, state = repository(tmp_path, monkeypatch)
    path = root / directories[0] / "large.bin"
    with path.open("wb") as stream:
        stream.truncate(pub.MAX_FILE_BYTES)
    seal(root, directories[0])
    with pytest.raises(ValueError, match="100_MiB"):
        pub.publish(root, directories, message="Synthetic")
    assert path.stat().st_size == pub.MAX_FILE_BYTES and not state["pushes"]


def test_active_clean_filter_is_blocked_before_git_add(tmp_path, monkeypatch):
    root, directories, state = repository(tmp_path, monkeypatch)
    (root / ".gitattributes").write_text("*.txt filter=synthetic\n")
    with pytest.raises(ValueError, match="active_Git_clean_filter"):
        pub.publish(root, directories, message="Synthetic")
    assert not git(root, "diff", "--cached", "--name-only") and not state["pushes"]


def test_text_attribute_normalization_cannot_silently_change_archived_bytes(tmp_path, monkeypatch):
    root, directories, state = repository(tmp_path, monkeypatch)
    start = git(root, "rev-parse", "HEAD")
    (root / ".gitattributes").write_text("*.txt text\n")
    with pytest.raises(ValueError, match="index_blob_not_original_raw_bytes"):
        pub.publish(root, directories, message="Synthetic")
    assert git(root, "rev-parse", "HEAD") == start and not state["pushes"]
    assert (root / directories[0] / "report.txt").read_bytes().endswith(b"\r\n")


@pytest.mark.parametrize("when", ["after_add", "before_commit"])
def test_uncooperating_staging_race_cannot_publish_unrelated_file(tmp_path, monkeypatch, when):
    root, directories, state = repository(tmp_path, monkeypatch)
    (root / "unrelated.txt").write_text("Other process data")
    state[when] = lambda: git(root, "add", "unrelated.txt")
    with pytest.raises(ValueError, match="outside_owned_scope"):
        pub.publish(root, directories, message="Synthetic")
    assert not state["pushes"] and (root / "unrelated.txt").read_text() == "Other process data"


def test_failed_push_preserves_commit_and_retry_does_not_recommit(tmp_path, monkeypatch):
    root, directories, state = repository(tmp_path, monkeypatch)
    previous = state["remote"]
    state["fail_push"] = True
    with pytest.raises(ValueError, match="git_push_failed") as raised:
        pub.publish(root, directories, message="Synthetic complete output")
    assert KEY not in str(raised.value)
    committed = git(root, "rev-parse", "HEAD")
    assert committed != previous and state["remote"] == previous
    state["fail_push"] = False
    result = pub.publish(root, directories, message="Should reuse already verified local commit")
    assert result["commit_id"] == committed and not result["new_commit_created"]
    assert state["remote"] == committed


def test_unpublished_unrelated_history_is_not_pushed_with_science_outputs(tmp_path, monkeypatch):
    root, directories, state = repository(tmp_path, monkeypatch)
    (root / "unrelated.txt").write_text("Unpublished unrelated change")
    git(root, "add", "unrelated.txt")
    git(root, "commit", "-q", "-m", "Unrelated unpublished work")
    with pytest.raises(ValueError, match="unpublished_changes_outside_owned_scope"):
        pub.publish(root, directories, message="Synthetic")
    assert not state["pushes"]


def test_runtime_fcntl_lock_is_exclusive_and_never_deleted(tmp_path, monkeypatch):
    root, directories, state = repository(tmp_path, monkeypatch)
    path = root / pub.LOCK_PATH
    path.parent.mkdir(parents=True)
    with path.open("a+b") as locked:
        fcntl.flock(locked.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ValueError, match="concurrent_publisher"):
            pub.publish(root, directories, message="Synthetic")
    assert path.is_file() and not state["pushes"]
