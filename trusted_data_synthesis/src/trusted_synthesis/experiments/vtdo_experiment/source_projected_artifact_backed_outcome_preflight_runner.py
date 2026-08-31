from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any, Final

AUTHORIZED_PREDECESSOR: Final = "fc48f9b770b8b9fbd1b5cf71096cde708e796f03"
PERMITTED_CHANGE_SURFACE: Final = (
    "trusted_data_synthesis/docs/current_project_status.md",
    "trusted_data_synthesis/docs/finance_v26_186_artifact_backed_outcome_preflight.md",
    "trusted_data_synthesis/src/trusted_synthesis/core/task/"
    "authoritative_artifact_backed_outcome.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_artifact_backed_outcome_preflight.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_artifact_backed_outcome_preflight_models.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "source_projected_artifact_backed_outcome_preflight_runner.py",
    "trusted_data_synthesis/tests/test_v26_capability_artifact_backed_outcome_preflight.py",
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
    with tarfile.open(path, mode="r:") as archive:
        archive.extractall(destination, filter="data")


def run_source_projected_preflight(
    *,
    repo_root: Path,
    source_commit: str,
    output_dir: Path,
    source_archive_output: Path,
) -> dict[str, Any]:
    root = repo_root.resolve()
    commit = _git(root, "rev-parse", f"{source_commit}^{{commit}}")
    tree = _git(root, "rev-parse", f"{commit}^{{tree}}")
    changes = tuple(_git(root, "diff", "--name-only", AUTHORIZED_PREDECESSOR, commit).splitlines())
    if changes != PERMITTED_CHANGE_SURFACE:
        raise ValueError("v26.186 source change surface is not the exact authorized set")
    for path in (output_dir, source_archive_output):
        if path.exists():
            raise FileExistsError(f"v26.186 output already exists:{path}")
    source_archive_output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        (
            "git",
            "archive",
            "--format=tar",
            f"--output={source_archive_output.resolve()}",
            commit,
        ),
        cwd=root,
        check=True,
    )
    with tempfile.TemporaryDirectory(prefix="v26-186-source-projected-") as temporary:
        source_root = Path(temporary) / "source"
        _extract(source_archive_output, source_root)
        package_root = source_root / "trusted_data_synthesis"
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(package_root / "src")
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            (
                sys.executable,
                "-m",
                (
                    "trusted_synthesis.experiments.vtdo_experiment."
                    "phase1_v26_capability_artifact_backed_outcome_preflight"
                ),
                "--package-root",
                str(package_root),
                "--output-dir",
                str(output_dir.resolve()),
                "--source-archive",
                str(source_archive_output.resolve()),
                "--source-commit",
                commit,
                "--source-tree",
                tree,
            ),
            cwd=package_root,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                "v26.186 source-projected preflight failed\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )
    return json.loads(result.stdout)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-archive-output", type=Path, required=True)
    args = parser.parse_args()
    report = run_source_projected_preflight(
        repo_root=args.repo_root,
        source_commit=args.source_commit,
        output_dir=args.output_dir,
        source_archive_output=args.source_archive_output,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
