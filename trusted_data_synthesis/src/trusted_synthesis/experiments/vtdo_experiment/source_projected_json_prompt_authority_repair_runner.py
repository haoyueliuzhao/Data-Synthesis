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

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_json_prompt_authority_repair as repair,
)

PERMITTED_CHANGE_SURFACE = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "json_explicit_exact_future_runner.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_json_prompt_authority_repair.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_json_prompt_authority_repair_models.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "source_projected_json_prompt_authority_repair_runner.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/vtdo_experiment/"
    "v179_source_snapshot_result_replay.py",
    "trusted_data_synthesis/tests/test_v26_json_prompt_authority_repair.py",
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


def _archive(root: Path, commit: str, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(f"source Archive already exists:{output}")
    subprocess.run(
        ("git", "archive", "--format=tar", f"--output={output.resolve()}", commit),
        cwd=root,
        check=True,
    )


def _run_module(
    *,
    module: str,
    package_root: Path,
    arguments: tuple[str, ...],
) -> dict[str, Any]:
    environment = os.environ.copy()
    environment.pop("DEEPSEEK_API_KEY", None)
    environment["PYTHONPATH"] = str(package_root / "src")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        (sys.executable, "-m", module, *arguments),
        cwd=package_root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"source-projected module failed:{module}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return json.loads(result.stdout)


def run_source_projected_repair(
    *,
    repo_root: Path,
    source_commit: str,
    output_dir: Path,
    external_audit_path: Path,
    v192_source_archive_output: Path,
    v179_source_archive_output: Path,
    current_source_archive_output: Path,
) -> dict[str, Any]:
    root = repo_root.resolve()
    current_commit = _git(root, "rev-parse", f"{source_commit}^{{commit}}")
    current_tree = _git(root, "rev-parse", f"{current_commit}^{{tree}}")
    changes = tuple(
        sorted(
            _git(
                root,
                "diff",
                "--name-only",
                "1b586f5aef7a5f64891ea4906cec2ecb7757242d",
                current_commit,
            ).splitlines()
        )
    )
    if changes != PERMITTED_CHANGE_SURFACE:
        raise ValueError("v26.193 source change surface is not the exact authorized set")
    if output_dir.exists():
        raise FileExistsError(f"v26.193 output already exists:{output_dir}")
    _archive(root, repair.AUDITED_V192_SOURCE_COMMIT, v192_source_archive_output)
    _archive(root, repair.V179_SOURCE_COMMIT, v179_source_archive_output)
    _archive(root, current_commit, current_source_archive_output)
    with tempfile.TemporaryDirectory(prefix="v26-193-source-projected-") as temporary:
        temporary_root = Path(temporary)
        current_source = temporary_root / "v193-source"
        _extract(current_source_archive_output, current_source)
        current_package = current_source / "trusted_data_synthesis"
        report = _run_module(
            module=(
                "trusted_synthesis.experiments.vtdo_experiment."
                "phase1_v26_json_prompt_authority_repair"
            ),
            package_root=current_package,
            arguments=(
                "--package-root",
                str(current_package),
                "--output-dir",
                str(output_dir.resolve()),
                "--external-audit",
                str(external_audit_path.resolve()),
                "--v192-source-archive",
                str(v192_source_archive_output.resolve()),
                "--v179-source-archive",
                str(v179_source_archive_output.resolve()),
                "--current-source-archive",
                str(current_source_archive_output.resolve()),
                "--current-source-commit",
                current_commit,
                "--current-source-tree",
                current_tree,
            ),
        )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--external-audit", type=Path, required=True)
    parser.add_argument("--v192-source-archive-output", type=Path, required=True)
    parser.add_argument("--v179-source-archive-output", type=Path, required=True)
    parser.add_argument("--current-source-archive-output", type=Path, required=True)
    args = parser.parse_args()
    report = run_source_projected_repair(
        repo_root=args.repo_root,
        source_commit=args.source_commit,
        output_dir=args.output_dir,
        external_audit_path=args.external_audit,
        v192_source_archive_output=args.v192_source_archive_output,
        v179_source_archive_output=args.v179_source_archive_output,
        current_source_archive_output=args.current_source_archive_output,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
