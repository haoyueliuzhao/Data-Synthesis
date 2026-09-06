"""Prepare a source-fixed panel, collect its sixteen sessions, or analyze read-only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import runner, stage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run", "analyze"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    parser.add_argument("--preparation", type=Path)
    parser.add_argument("--execution", type=Path)
    parser.add_argument("--design", type=Path)
    parser.add_argument("--run-tag", default="fixed_eight_task_panel_v1_20260906")
    args = parser.parse_args()
    if args.command == "prepare":
        if args.output is None or args.design is None:
            parser.error("prepare requires --output and --design")
        result = stage.prepare(args.root, args.output, args.design, run_tag=args.run_tag)
    elif args.command == "run":
        if args.preparation is None:
            parser.error("run requires --preparation")
        result = runner.run(args.root, args.preparation)
    else:
        if args.preparation is None or args.execution is None or args.output is None:
            parser.error("analyze requires --preparation, --execution and --output")
        result = runner.analyze(args.root, args.preparation, args.execution, args.output)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
