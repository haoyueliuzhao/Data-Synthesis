"""Explicit preparation and CPU-only adaptation; no online execution command."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import runner


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run", "verify"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preparation", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        result = runner.prepare(args.root, args.output)
    elif args.command == "run":
        if args.preparation is None:
            parser.error("run requires --preparation")
        result = runner.run(args.root, args.preparation, args.output)
    else:
        result = runner.verify(args.output)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
