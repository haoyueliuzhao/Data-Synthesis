from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from trusted_synthesis.experiments.qa_realization_vnext.release_authority_envelope import (
    AUTHORIZED_PREDECESSOR,
    PERMITTED_CHANGE_SURFACE,
)
from trusted_synthesis.experiments.qa_realization_vnext.release_authority_envelope_preflight import (  # noqa: E501
    extract_git_archive,
)


def _git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ("git", *args),
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def run_source_projected_release_authority(
    *,
    repo_root: Path,
    source_commit_id: str,
    external_audit_path: Path,
    output_dir: Path,
    source_archive_output: Path | None = None,
) -> dict[str, object]:
    """Generate one Git archive, extract it, and execute only its authority code."""

    resolved_repo = repo_root.resolve()
    resolved_output = output_dir.resolve()
    source_commit = _git(resolved_repo, "rev-parse", f"{source_commit_id}^{{commit}}")
    source_tree = _git(resolved_repo, "rev-parse", f"{source_commit}^{{tree}}")
    observed_changes = tuple(
        line
        for line in _git(
            resolved_repo,
            "diff",
            "--name-only",
            AUTHORIZED_PREDECESSOR,
            source_commit,
        ).splitlines()
        if line
    )
    if observed_changes != PERMITTED_CHANGE_SURFACE:
        raise ValueError("Git implementation change surface differs from external authorization")
    if resolved_output.exists():
        raise FileExistsError(f"immutable authority output already exists: {resolved_output}")

    with tempfile.TemporaryDirectory(prefix="qa-release-source-projection-") as temporary:
        temporary_root = Path(temporary)
        source_archive = (
            source_archive_output.resolve()
            if source_archive_output is not None
            else temporary_root / "source.tar"
        )
        if source_archive.exists():
            raise FileExistsError(f"source archive output already exists: {source_archive}")
        source_archive.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            (
                "git",
                "archive",
                "--format=tar",
                f"--output={source_archive}",
                source_commit,
            ),
            cwd=resolved_repo,
            check=True,
        )
        extracted_root = temporary_root / "extracted"
        extract_git_archive(source_archive, extracted_root)
        observed_change_path = temporary_root / "observed_change_surface.json"
        observed_change_path.write_text(
            json.dumps(observed_changes, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(extracted_root / "trusted_data_synthesis" / "src")
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            (
                sys.executable,
                "-m",
                (
                    "trusted_synthesis.experiments.qa_realization_vnext."
                    "release_authority_envelope_preflight"
                ),
                "--source-commit-id",
                source_commit,
                "--source-tree-id",
                source_tree,
                "--source-archive",
                str(source_archive),
                "--external-audit",
                str(external_audit_path.resolve()),
                "--observed-change-surface",
                str(observed_change_path),
                "--output-dir",
                str(resolved_output),
            ),
            cwd=extracted_root,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
    return json.loads(result.stdout)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--source-commit-id", required=True)
    parser.add_argument("--external-audit", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-archive-output", type=Path)
    args = parser.parse_args()
    report = run_source_projected_release_authority(
        repo_root=args.repo_root,
        source_commit_id=args.source_commit_id,
        external_audit_path=args.external_audit,
        output_dir=args.output_dir,
        source_archive_output=args.source_archive_output,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
