"""Only additive preparation and zero-execution measurement; no generation entry."""

import argparse
import json
from pathlib import Path

from .stage import ARTIFACT_PREFIX, RUN_TAG, prepare, run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "run"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = (prepare if args.phase == "prepare" else run)(
        args.root, args.output or args.root / ARTIFACT_PREFIX / RUN_TAG
    )
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "id",
                    "stage",
                    "source_commit",
                    "mapped_qualified_sessions",
                    "assignment_count",
                    "formal_class_count",
                    "new_W_support",
                    "complete_quotient_measurement_closed",
                    "newly_interpreted_events",
                    "unresolved_labels",
                )
                if k in result
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
