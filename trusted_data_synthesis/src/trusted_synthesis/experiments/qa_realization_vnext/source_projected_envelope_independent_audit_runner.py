from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any

from trusted_synthesis.experiments.qa_realization_vnext import (
    release_authority_envelope_independent_audit as audit,
)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ("git", *args),
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _extract(path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    with tarfile.open(path, mode="r:") as source:
        source.extractall(destination, filter="data")


def run_source_projected_audit(
    *,
    repo_root: Path,
    source_commit: str,
    external_audit: Path,
    output_dir: Path,
    audit_archive_output: Path,
    predecessor_archive_output: Path,
) -> dict[str, Any]:
    root = repo_root.resolve()
    commit = _git(root, "rev-parse", f"{source_commit}^{{commit}}")
    tree = _git(root, "rev-parse", f"{commit}^{{tree}}")
    changes = tuple(
        _git(root, "diff", "--name-only", audit.AUTHORIZED_PREDECESSOR, commit).splitlines()
    )
    if changes != audit.PERMITTED_CHANGE_SURFACE:
        raise ValueError("independent audit source change surface is not exact")
    for path in (output_dir, audit_archive_output, predecessor_archive_output):
        if path.exists():
            raise FileExistsError(f"output already exists: {path}")
    audit_archive_output.parent.mkdir(parents=True, exist_ok=True)
    predecessor_archive_output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        (
            "git",
            "archive",
            "--format=tar",
            f"--output={audit_archive_output.resolve()}",
            commit,
        ),
        cwd=root,
        check=True,
    )
    subprocess.run(
        (
            "git",
            "archive",
            "--format=tar",
            f"--output={predecessor_archive_output.resolve()}",
            audit.AUDITED_SOURCE_COMMIT,
        ),
        cwd=root,
        check=True,
    )
    with tempfile.TemporaryDirectory(prefix="v26-185-source-projected-") as temporary:
        temporary_root = Path(temporary)
        source_root = temporary_root / "source"
        artifact_snapshot = temporary_root / "artifact-snapshot"
        _extract(audit_archive_output, source_root)
        artifact_archive = temporary_root / "artifacts.tar"
        subprocess.run(
            (
                "git",
                "archive",
                "--format=tar",
                f"--output={artifact_archive}",
                audit.AUDITED_ARTIFACT_COMMIT,
                "--",
                audit.AUDITED_ARTIFACT_DIR,
            ),
            cwd=root,
            check=True,
        )
        _extract(artifact_archive, artifact_snapshot)
        changes_path = temporary_root / "changes.json"
        changes_path.write_text(json.dumps(changes) + "\n", encoding="utf-8")
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(source_root / "trusted_data_synthesis" / "src")
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            (
                sys.executable,
                "-m",
                (
                    "trusted_synthesis.experiments.qa_realization_vnext."
                    "release_authority_envelope_independent_audit"
                ),
                "--audit-source-commit",
                commit,
                "--audit-source-tree",
                tree,
                "--audit-source-archive",
                str(audit_archive_output.resolve()),
                "--predecessor-source-archive",
                str(predecessor_archive_output.resolve()),
                "--artifact-snapshot-dir",
                str(artifact_snapshot),
                "--external-audit",
                str(external_audit.resolve()),
                "--observed-change-surface",
                str(changes_path),
                "--output-dir",
                str(output_dir.resolve()),
            ),
            cwd=source_root,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
    return json.loads(result.stdout)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--external-audit", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--audit-archive-output", type=Path, required=True)
    parser.add_argument("--predecessor-archive-output", type=Path, required=True)
    args = parser.parse_args()
    report = run_source_projected_audit(
        repo_root=args.repo_root,
        source_commit=args.source_commit,
        external_audit=args.external_audit,
        output_dir=args.output_dir,
        audit_archive_output=args.audit_archive_output,
        predecessor_archive_output=args.predecessor_archive_output,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
