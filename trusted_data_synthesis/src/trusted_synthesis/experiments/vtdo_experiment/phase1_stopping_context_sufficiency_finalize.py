from __future__ import annotations

import argparse
from pathlib import Path

from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_context_sufficiency_runner import (  # noqa: E501
    finalize_context_sufficiency_run,
)

FINALIZER_VERSION = "finance_stopping_context_sufficiency_finalizer.v1"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=("Disaster-recovery finalizer for a completed Finance v25.47 API execution")
    )
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    finalize_context_sufficiency_run(
        contract_path=args.contract,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
