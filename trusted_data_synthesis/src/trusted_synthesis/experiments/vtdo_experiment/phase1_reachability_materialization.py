from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from trusted_synthesis.core.vtdo import (
    AnchoredDistributionUpdate,
    ValidTrajectoryStateMaterializer,
)
from trusted_synthesis.experiments.vtdo_experiment.multistate import (
    load_finance_multi_state_artifacts,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_mvp import (
    Phase1DeterministicMaterializer,
    _make_evaluator,
    _subcatalog,
)
from trusted_synthesis.hashing import canonical_hash

REACHABILITY_MATERIALIZATION_VERSION = (
    "finance_phase1_reachability_materialization.v1"
)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run(args: argparse.Namespace) -> None:
    update_path = Path(args.update_path).resolve()
    artifacts_path = Path(args.artifacts_path).resolve()
    archive_config_path = Path(args.archive_config_path).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    update = AnchoredDistributionUpdate.model_validate_json(
        update_path.read_text(encoding="utf-8")
    )
    if update.reachability_manifest is None:
        raise ValueError("materialization requires a reachability-aware update")
    artifact = next(
        (
            item
            for item in load_finance_multi_state_artifacts(artifacts_path)
            if item.omega.task.task_id
            == update.prior_distribution.task_condition_id
        ),
        None,
    )
    if artifact is None:
        raise ValueError("target task is absent from the multi-state artifacts")
    support = set(update.next_distribution.probabilities)
    states = tuple(
        item
        for item in artifact.accepted_states
        if item.assignment.state.state_id in support
    )
    if {item.assignment.state.state_id for item in states} != support:
        raise ValueError("accepted states do not cover update support")
    catalog = _subcatalog(artifact, states)
    evaluator = _make_evaluator(archive_config_path)
    materialized, materialization_report = ValidTrajectoryStateMaterializer(
        Phase1DeterministicMaterializer(states, catalog),
        evaluator,
    ).materialize(
        artifact.omega,
        catalog,
        update.next_distribution,
        update.role_contract,
        total_budget=args.budget,
        seed=args.seed,
        maximum_attempt_multiplier=2,
    )
    strategy_by_state = {
        item.assignment.state.state_id: item.strategy for item in states
    }
    strategy_counts = Counter(
        strategy_by_state[item.target_state.state_id] for item in materialized
    )
    released_count = len(materialized)
    summary: dict[str, Any] = {
        "experiment_version": REACHABILITY_MATERIALIZATION_VERSION,
        "source_update_id": update.update_id,
        "reachability_manifest_id": update.reachability_manifest.manifest_id,
        "task_condition_id": update.prior_distribution.task_condition_id,
        "requested_budget": args.budget,
        "released_count": released_count,
        "quota_fill_rate": materialization_report.quota_fill_rate,
        "generation_acceptance_rate": (
            materialization_report.generation_acceptance_rate
        ),
        "distribution_total_variation": (
            materialization_report.distribution_total_variation
        ),
        "failure_counts": materialization_report.failure_counts,
        "released_state_distribution": (
            materialization_report.released_state_distribution
        ),
        "released_strategy_counts": dict(sorted(strategy_counts.items())),
        "status": (
            "passed"
            if released_count == args.budget
            and materialization_report.quota_fill_rate == 1.0
            and materialization_report.generation_acceptance_rate == 1.0
            else "partial"
        ),
        "claim_boundary": (
            "Controlled deterministic materialization validates quota realization and "
            "independent verification, not LLM state-conditioned generation reliability."
        ),
    }
    summary["summary_hash"] = canonical_hash(
        summary,
        prefix="finance_reachability_materialization:",
    )
    (output_dir / "materialized_artifacts.jsonl").write_text(
        "".join(item.model_dump_json() + "\n" for item in materialized),
        encoding="utf-8",
    )
    (output_dir / "materialization_report.json").write_text(
        materialization_report.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    _write_json(output_dir / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Materialize a reachability-aware Phase 1 distribution"
    )
    parser.add_argument("--update-path", required=True)
    parser.add_argument("--artifacts-path", required=True)
    parser.add_argument("--archive-config-path", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--budget", type=int, default=30)
    parser.add_argument("--seed", type=int, default=20260804)
    return parser


def main() -> None:
    run(_parser().parse_args())


if __name__ == "__main__":
    main()
