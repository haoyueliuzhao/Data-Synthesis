"""Explicit zero-call preparation, at-most-once run, and immutable reanalysis."""

import argparse
import json
from pathlib import Path

from .runner import analyze, prepare, run


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("command", choices=("prepare", "run", "analyze"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--preparation", type=Path, required=True)
    parser.add_argument("--design", type=Path)
    parser.add_argument("--run-tag")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        if args.design is None or args.run_tag is None:
            parser.error("prepare requires --design and --run-tag")
        result = prepare(args.root, args.preparation, args.design, run_tag=args.run_tag)
    elif args.command == "run":
        result = run(args.root, args.preparation)
    else:
        if args.output is None:
            parser.error("analyze requires --output")
        result = analyze(
            args.root, args.preparation, args.preparation.parent / "execution", args.output
        )
    print(
        json.dumps(
            {
                key: value
                for key, value in result.items()
                if key
                in {
                    "id",
                    "stage",
                    "provider_attempt_count",
                    "candidate_count",
                    "measurement",
                    "scientific_objects",
                    "workflow_evidence_complete",
                    "prepared",
                }
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
