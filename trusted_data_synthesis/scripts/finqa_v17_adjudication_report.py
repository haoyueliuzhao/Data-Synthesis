#!/usr/bin/env python3
"""Read-only summary of the three additional explicitly authorized judgments."""

import argparse
from pathlib import Path

from finqa_v16_adjudication_report import summarize

from trusted_synthesis.finance_research.v17_registration import OUTPUT

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    result = summarize(
        args.output,
        args.destination,
        expected_calls=3,
        expected_packages=13,
        inherited_tasks=741,
        schema="v17_actual_three_task_report.v1",
    )
    print(
        {
            k: result[k]
            for k in ("id", "returned", "usable", "settled_upper_bound_microcny", "tokens")
        }
    )
