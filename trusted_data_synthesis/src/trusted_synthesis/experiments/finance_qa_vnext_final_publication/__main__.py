"""Only frozen preparation and one bounded online execution; no resampling entry."""

import argparse
import json
from pathlib import Path

from .plan import RUN_TAG
from .runner import run
from .stage import ARTIFACT_PREFIX, prepare


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "run"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or args.root / ARTIFACT_PREFIX / RUN_TAG
    result = (prepare if args.phase == "prepare" else run)(args.root, output)
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "id",
                    "stage",
                    "source_commit",
                    "provider_attempt_count",
                    "status_counts",
                    "candidate_count",
                    "token_fit_count",
                )
                if key in result
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
