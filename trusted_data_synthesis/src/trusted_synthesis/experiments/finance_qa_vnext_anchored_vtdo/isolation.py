"""Application-level input separation, not a claim of a hostile-code sandbox."""

import argparse
import subprocess
from pathlib import Path

from . import protocol as p


def independent_checkout(root, live_root):
    root, live_root = Path(root).resolve(), Path(live_root).resolve()
    p.require(root != live_root, "isolation.distinct_worktree_required")
    branch = subprocess.check_output(
        ["git", "branch", "--show-current"], cwd=root, text=True
    ).strip()
    p.require(branch == p.BRANCH, "isolation.only_new_algorithm_branch")
    top = subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], cwd=root, text=True
    ).strip()
    p.require(Path(top).resolve() == root, "isolation.exact_new_worktree_root")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    return p.record(
        "independent_worktree",
        worktree=str(root),
        live_worktree=str(live_root),
        branch=branch,
        commit=commit,
        main_checked_out_here=False,
    )


def confirmation_presence(live_root):
    """Only stat predeclared paths. Never open scores, outcomes or checkpoints."""
    live_root = Path(live_root).resolve()
    names = (
        "preparation",
        "training",
        "generation/confirm",
        "scores/confirm",
        "decision.json",
        "confirmation.json",
        "report.json",
    )
    rows = []
    for relative in names:
        path = live_root / p.PROTECTED_STUDY / relative
        p.require(
            not any(item.is_symlink() for item in (path, *path.parents)),
            "isolation.no_metadata_symlink",
        )
        present = path.exists()
        rows.append(
            {
                "relative_path": str(Path(p.PROTECTED_STUDY) / relative),
                "exists": present,
                "mtime_ns": path.stat().st_mtime_ns if present else None,
            }
        )
    return p.record(
        "confirmation_presence_observation",
        observed_at=p.now(),
        paths=rows,
        contents_opened=0,
        scores_or_outcomes_read=0,
        absence_proves_never_computed=False,
        absence_or_unpublished_report_is_not_confirmation_independence=True,
    )


class DevelopmentReader:
    """Explicit caller allowlist, always excluding this baseline's Student output."""

    def __init__(self, root, allowed_paths):
        self.root = Path(root).resolve()
        self.allowed = frozenset(str(name) for name in allowed_paths)
        self.accesses = []

    def read(self, relative):
        relative = Path(relative)
        text = str(relative)
        p.require(
            not relative.is_absolute() and ".." not in relative.parts,
            "isolation.relative_read_only",
        )
        p.require(
            not (text == p.PROTECTED_STUDY or text.startswith(p.PROTECTED_STUDY + "/")),
            "isolation.baseline_Student_outputs_forbidden_for_algorithm_development",
        )
        p.require(
            "confirm" not in relative.parts and "confirmation.json" != relative.name,
            "isolation.no_confirmation_feedback_or_design_input",
        )
        p.require(text in self.allowed, "isolation.exact_read_allowlist")
        path = self.root / relative
        p.require(
            path.resolve().is_relative_to(self.root)
            and not any(item.is_symlink() for item in (path, *path.parents)),
            "isolation.no_symlink_read",
        )
        data = path.read_bytes()
        self.accesses.append({"path": text, "sha256": p.sha(data), "bytes": len(data)})
        return data


def new_output(root, relative):
    root, relative = Path(root).resolve(), Path(relative)
    prefix = Path(p.OUTPUT)
    p.require(
        not relative.is_absolute()
        and ".." not in relative.parts
        and relative.is_relative_to(prefix)
        and relative != prefix,
        "isolation.dedicated_new_algorithm_output",
    )
    path = root / relative
    p.require(
        path.resolve().is_relative_to(root)
        and not any(item.is_symlink() for item in (path, *path.parents)),
        "isolation.no_output_symlink",
    )
    p.require(not path.exists(), "isolation.no_output_overwrite_or_reexecution")
    return path


def require_production_authorization():
    p.require(False, "anchored.new_GPU_feedback_budget_and_production_adapter_not_authorized")


def prepare_branch(root, live_root):
    root, live_root = Path(root).resolve(), Path(live_root).resolve()
    checkout = independent_checkout(root, live_root)
    output = new_output(root, p.OUTPUT + "/branch_preparation_20260913")
    paths = subprocess.check_output(
        [
            "git",
            "ls-tree",
            "-r",
            "--name-only",
            p.BASE_COMMIT,
            "--",
            "trusted_data_synthesis/src",
            "trusted_data_synthesis/tests",
            "raw_financial_data_lake/finraw",
            "raw_financial_data_lake/tests",
        ],
        cwd=root,
        text=True,
    ).splitlines()
    protected = [
        {"path": name, "sha256": p.sha(live_root / name)} for name in paths if name.endswith(".py")
    ]
    result = p.record(
        "branch_start",
        created_at=p.now(),
        checkout=checkout,
        starting_algorithm_proposal=p.policy(),
        live_source_files=protected,
        confirmation_presence=confirmation_presence(live_root),
        confirmed_outcomes_read_for_this_development=False,
        actual_baseline_Student_outputs_inspected=False,
        source_files_hashed_only=True,
        main_writes=0,
        new_GPU_calls=0,
        new_Teacher_or_probe_calls=0,
        live_ledger_opened=False,
        final_algorithm_or_actual_study_freeze=False,
    )
    p.write_once(output / "branch_start.json", result)
    return {
        "id": result["id"],
        "output": str(output),
        "protected_sources": len(protected),
        "confirmation_contents_read": 0,
    }


def check_protected_sources(root, live_root):
    root, live_root = Path(root).resolve(), Path(live_root).resolve()
    start = p.checked_record(
        p.read_json(root / p.OUTPUT / "branch_preparation_20260913/branch_start.json"),
        "branch_start",
    )
    changed = [
        row["path"]
        for row in start["live_source_files"]
        if p.sha(live_root / row["path"]) != row["sha256"]
    ]
    p.require(not changed, "isolation.live_production_sources_changed")
    return p.record(
        "protected_sources_check",
        at=p.now(),
        branch_start_id=start["id"],
        source_count=len(start["live_source_files"]),
        mismatches=0,
        live_outcome_or_ledger_contents_read=0,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "verify"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--live-root", type=Path, required=True)
    arguments = parser.parse_args()
    result = {"prepare": prepare_branch, "verify": check_protected_sources}[arguments.phase](
        arguments.root, arguments.live_root
    )
    print(p.encode(result).decode())
