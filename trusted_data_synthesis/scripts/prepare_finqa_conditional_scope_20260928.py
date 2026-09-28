"""Freeze static author-evidence scope before any paid Probe generation."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory
from trusted_synthesis.finance_research.calibration import CACHE
from trusted_synthesis.finance_research.probe_scope import build_conditional_scope
from trusted_synthesis.finance_research.storage import encode, read_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    scope = build_conditional_scope(read_json(CACHE / "reference_revision_01/protocol.json"))
    count = len(scope["task_ids"])
    summary = dict(
        scope_id=scope["scope_id"],
        original_candidate_count=1000,
        conditional_task_count=count,
        excluded_task_count=1000 - count,
        excluded_reasons=dict(
            Counter(row["reason"] for row in scope["coverage_rows"] if not row["included"])
        ),
        max_episodes=count * 8,
        train_slots=count * 6,
        sealed_slots=count * 2,
        maximum_model_requests=count * 8 * 32,
        actual_model_requests=0,
        private_answers_sent_to_Probe=False,
        static_applicability_is_not_material_qualification=True,
        original_1000_training_admitted=False,
    )
    write_immutable_artifact_directory(
        args.output, {"record.json": encode(scope), "summary.json": encode(summary)}
    )
    print(encode(summary).decode())


if __name__ == "__main__":
    main()
