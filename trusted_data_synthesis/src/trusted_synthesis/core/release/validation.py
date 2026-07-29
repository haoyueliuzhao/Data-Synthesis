from __future__ import annotations

import hashlib
import importlib.metadata
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis import __version__
from trusted_synthesis.hashing import canonical_hash

RELEASE_VALIDATION_SUMMARY_VERSION = "release_validation_summary.v1"


class ReleaseValidationSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    summary_id: str
    commit_sha: str
    git_worktree_dirty: bool
    test_command: str
    test_count: int = Field(ge=0)
    test_status: Literal["passed", "failed", "not_run"]
    tool_versions: dict[str, str]
    artifact_hashes: dict[str, str]
    online_status: Literal["not_run", "offline_only", "online_passed", "online_failed"]
    supersedes: tuple[str, ...] = ()
    created_at: str
    status: Literal["passed", "failed", "partial"]
    version: str = RELEASE_VALIDATION_SUMMARY_VERSION

    @model_validator(mode="after")
    def validate_status(self) -> ReleaseValidationSummary:
        if self.test_status == "failed" or self.online_status == "online_failed":
            expected = "failed"
        elif self.git_worktree_dirty:
            expected = "partial"
        elif (
            self.test_status == "passed"
            and self.online_status in {"offline_only", "online_passed"}
            and self.artifact_hashes
        ):
            expected = "passed"
        else:
            expected = "partial"
        if self.status != expected:
            raise ValueError(f"release validation status must be {expected}")
        return self


def build_release_validation_summary(
    *,
    repo_root: Path,
    artifacts: tuple[Path, ...],
    test_command: str,
    test_count: int,
    test_status: Literal["passed", "failed", "not_run"],
    online_status: Literal[
        "not_run", "offline_only", "online_passed", "online_failed"
    ] = "offline_only",
    supersedes: tuple[str, ...] = (),
    commit_sha: str | None = None,
    git_worktree_dirty: bool | None = None,
    tool_versions: dict[str, str] | None = None,
) -> ReleaseValidationSummary:
    root = repo_root.resolve()
    resolved_commit = commit_sha or _git_output(root, "rev-parse", "HEAD")
    resolved_dirty = (
        git_worktree_dirty
        if git_worktree_dirty is not None
        else bool(_git_output(root, "status", "--porcelain"))
    )
    artifact_hashes: dict[str, str] = {}
    for artifact in artifacts:
        path = artifact.resolve()
        if not path.is_file():
            raise ValueError(f"release validation artifact does not exist: {path}")
        try:
            key = path.relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError("release validation artifacts must be inside repo_root") from exc
        artifact_hashes[key] = _file_sha256(path)
    versions = tool_versions or _tool_versions()
    status: Literal["passed", "failed", "partial"]
    if test_status == "failed" or online_status == "online_failed":
        status = "failed"
    elif resolved_dirty:
        status = "partial"
    elif test_status == "passed" and online_status in {"offline_only", "online_passed"}:
        status = "passed" if artifact_hashes else "partial"
    else:
        status = "partial"
    created_at = datetime.now(timezone.utc).isoformat()
    identity = {
        "commit_sha": resolved_commit,
        "git_worktree_dirty": resolved_dirty,
        "test_command": test_command,
        "test_count": test_count,
        "test_status": test_status,
        "tool_versions": versions,
        "artifact_hashes": artifact_hashes,
        "online_status": online_status,
        "supersedes": supersedes,
        "version": RELEASE_VALIDATION_SUMMARY_VERSION,
    }
    return ReleaseValidationSummary(
        summary_id=canonical_hash(identity, prefix="release_validation_summary:"),
        commit_sha=resolved_commit,
        git_worktree_dirty=resolved_dirty,
        test_command=test_command,
        test_count=test_count,
        test_status=test_status,
        tool_versions=dict(sorted(versions.items())),
        artifact_hashes=dict(sorted(artifact_hashes.items())),
        online_status=online_status,
        supersedes=supersedes,
        created_at=created_at,
        status=status,
    )


def _git_output(repo_root: Path, *arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments],
        cwd=repo_root,
        text=True,
        stderr=subprocess.DEVNULL,
    ).strip()


def _tool_versions() -> dict[str, str]:
    versions = {
        "python": sys.version.split()[0],
        "trusted-data-synthesis": __version__,
    }
    for distribution in ("pydantic", "pytest", "ruff"):
        try:
            versions[distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            versions[distribution] = "not_installed"
    return versions


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
