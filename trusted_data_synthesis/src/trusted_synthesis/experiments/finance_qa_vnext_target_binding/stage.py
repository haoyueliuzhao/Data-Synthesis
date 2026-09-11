"""Explicit zero-model phases; no training or provider command exists here."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from . import cases, failure_structure, ledger
from .core import TEST, ZeroModelGuard, history_guard, require


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "phase",
        choices=(
            "freeze-ledger",
            "failure-structure",
            "prepare-cases",
            "show-cases",
            "finalize-cases",
            "closeout",
        ),
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--reviews", type=Path)
    parser.add_argument("--first", type=int, default=1)
    parser.add_argument("--last", type=int, default=1)
    args = parser.parse_args()
    root = args.root.resolve()
    integrity = history_guard(root)
    controls = None
    if args.phase == "freeze-ledger":
        command = [sys.executable, "-B", "-m", "pytest", "-q", TEST]
        completed = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            check=False,
            env={**os.environ, "PYTHONPATH": str(root / "trusted_data_synthesis/src")},
        )
        require(completed.returncode == 0, "stage.new_pure_controls_must_pass")
        controls = {
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    with ZeroModelGuard(root) as guard:
        if args.phase == "freeze-ledger":
            result = ledger.build(root, guard, controls)
        elif args.phase == "failure-structure":
            result = failure_structure.build(root, guard)
        elif args.phase == "prepare-cases":
            result = cases.prepare(root, guard)
        elif args.phase == "show-cases":
            cases.show(root, args.first, args.last)
            result = None
        elif args.phase == "finalize-cases":
            if args.reviews is None:
                parser.error("--reviews is required for finalize-cases")
            result = cases.finalize(root, args.reviews, guard)
        else:
            result = cases.closeout(root, guard, integrity)
    history_guard(root)
    if result is not None:
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
