from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from trusted_synthesis.core.vtdo import (
    AnchoredDistributionUpdate,
    StateReachabilityManifest,
    update_valid_trajectory_distribution,
)
from trusted_synthesis.core.vtdo.schema import state_reachability_manifest_id
from trusted_synthesis.experiments.vtdo_experiment.multistate import (
    FinanceTaskStateArtifact,
    load_finance_multi_state_artifacts,
)
from trusted_synthesis.hashing import canonical_hash

REACHABILITY_ANALYSIS_VERSION = "finance_phase1_reachability_analysis.v1"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _entropy(counts: Counter[str]) -> float:
    total = sum(counts.values())
    if not total:
        return 0.0
    return -sum((count / total) * math.log(count / total) for count in counts.values() if count)


def _subset_manifest(
    manifest: StateReachabilityManifest,
    support: set[str],
) -> StateReachabilityManifest:
    estimates = tuple(item for item in manifest.estimates if item.state_id in support)
    if {item.state_id for item in estimates} != support:
        raise ValueError("reachability manifest does not cover update support")
    values = {
        "task_condition_id": manifest.task_condition_id,
        "explorer_provider_id": manifest.explorer_provider_id,
        "explorer_provider_version": manifest.explorer_provider_version,
        "estimates": estimates,
        "source_batch_ids": manifest.source_batch_ids,
        "schema_version": manifest.schema_version,
    }
    provisional = StateReachabilityManifest.model_construct(
        manifest_id="pending",
        **values,
    )
    return StateReachabilityManifest(
        manifest_id=state_reachability_manifest_id(provisional),
        **values,
    )


def _strategy_index(
    artifacts: tuple[FinanceTaskStateArtifact, ...],
) -> dict[tuple[str, str], str]:
    return {
        (artifact.omega.task.task_id, state.assignment.state.state_id): state.strategy
        for artifact in artifacts
        for state in artifact.accepted_states
    }


def _mass_by_strategy(
    probabilities: Mapping[str, float],
    strategies: Mapping[str, str],
) -> dict[str, float]:
    result: defaultdict[str, float] = defaultdict(float)
    for state_id, probability in probabilities.items():
        result[strategies[state_id]] += probability
    return dict(sorted(result.items()))


def _profile(
    archived: AnchoredDistributionUpdate,
    manifest: StateReachabilityManifest,
    strategies: Mapping[str, str],
    *,
    signal: Literal["posterior_mean", "confidence_lower"],
    weight: float,
) -> dict[str, Any]:
    config = archived.energy_config.model_copy(
        update={
            "reachability_weight": weight,
            "reachability_floor": 0.01,
            "reachability_signal": signal,
        }
    )
    update = update_valid_trajectory_distribution(
        archived.prior_distribution,
        archived.coverage_prior,
        archived.validity_estimates,
        archived.contribution_manifest,
        archived.contribution_approximation_authorization,
        config,
        archived.role_contract,
        manifest,
    )
    observed = {item.state_id for item in manifest.estimates if item.on_target_trajectory_count > 0}
    probabilities = update.next_distribution.probabilities
    return {
        "reachability_signal": signal,
        "reachability_weight": weight,
        "update_id": update.update_id,
        "total_variation_from_pi0": update.total_variation_from_history,
        "kl_to_history": update.kl_to_history,
        "kl_to_coverage": update.kl_to_coverage,
        "entropy": update.next_entropy,
        "observed_state_mass": sum(
            value for state_id, value in probabilities.items() if state_id in observed
        ),
        "strategy_mass": _mass_by_strategy(probabilities, strategies),
        "probabilities": probabilities,
    }


def run(args: argparse.Namespace) -> None:
    experiment_dir = Path(args.experiment_dir).resolve()
    artifacts = load_finance_multi_state_artifacts(Path(args.artifacts_path).resolve())
    artifacts_by_task = {item.omega.task.task_id: item for item in artifacts}
    strategy_by_task_state = _strategy_index(artifacts)
    records = _read_jsonl(experiment_dir / "exploration_records.jsonl")
    manifests = {
        item.task_condition_id: item
        for item in (
            StateReachabilityManifest.model_validate(value)
            for value in _read_jsonl(experiment_dir / "reachability_manifests.jsonl")
        )
    }
    archived = AnchoredDistributionUpdate.model_validate_json(
        (Path(args.phase1_aggregate_dir).resolve() / "anchored_distribution_update.json").read_text(
            encoding="utf-8"
        )
    )
    target_task_id = archived.prior_distribution.task_condition_id
    target_manifest = _subset_manifest(
        manifests[target_task_id],
        set(archived.prior_distribution.probabilities),
    )
    target_artifact = artifacts_by_task[target_task_id]
    target_strategies = {
        state.assignment.state.state_id: state.strategy
        for state in target_artifact.accepted_states
        if state.assignment.state.state_id in archived.prior_distribution.probabilities
    }
    if set(target_strategies) != set(archived.prior_distribution.probabilities):
        raise ValueError("target strategies do not cover update support")

    valid_unconditioned = [
        item
        for item in records
        if item["mode"] == "unconditioned"
        and item["status"] == "completed"
        and item["validity_report"]["valid"]
    ]
    per_task_counts: defaultdict[str, Counter[str]] = defaultdict(Counter)
    strategy_counts: Counter[str] = Counter()
    for item in valid_unconditioned:
        state_id = item["state_assignment"]["state"]["state_id"]
        task_id = item["task_id"]
        per_task_counts[task_id][state_id] += 1
        strategy_counts[strategy_by_task_state[(task_id, state_id)]] += 1
    within_task_entropies = {
        task_id: _entropy(counts) for task_id, counts in sorted(per_task_counts.items())
    }

    observed = {
        item.state_id for item in target_manifest.estimates if item.on_target_trajectory_count > 0
    }
    baseline_probabilities = archived.next_distribution.probabilities
    profiles: list[dict[str, Any]] = [
        {
            "reachability_signal": "disabled",
            "reachability_weight": 0.0,
            "update_id": archived.update_id,
            "total_variation_from_pi0": archived.total_variation_from_history,
            "kl_to_history": archived.kl_to_history,
            "kl_to_coverage": archived.kl_to_coverage,
            "entropy": archived.next_entropy,
            "observed_state_mass": sum(
                value for state_id, value in baseline_probabilities.items() if state_id in observed
            ),
            "strategy_mass": _mass_by_strategy(
                baseline_probabilities,
                target_strategies,
            ),
            "probabilities": baseline_probabilities,
        }
    ]
    sensitivity_grid: tuple[
        tuple[Literal["posterior_mean", "confidence_lower"], tuple[float, ...]],
        ...,
    ] = (
        ("posterior_mean", (0.5, 1.0, 2.0, 4.0)),
        ("confidence_lower", (0.5, 1.0, 2.0)),
    )
    profiles.extend(
        _profile(
            archived,
            target_manifest,
            target_strategies,
            signal=signal,
            weight=weight,
        )
        for signal, weights in sensitivity_grid
        for weight in weights
    )
    interval_widths = [
        item.confidence_upper - item.confidence_lower
        for manifest in manifests.values()
        for item in manifest.estimates
    ]
    report: dict[str, Any] = {
        "analysis_version": REACHABILITY_ANALYSIS_VERSION,
        "source_summary_hash": _read_json(experiment_dir / "summary.json")["summary_hash"],
        "target_task_id": target_task_id,
        "unconditioned_valid_trajectory_count": len(valid_unconditioned),
        "task_count": len(per_task_counts),
        "cross_task_conditioned_state_id_count": len(
            {item["state_assignment"]["state"]["state_id"] for item in valid_unconditioned}
        ),
        "mean_within_task_state_entropy": (
            sum(within_task_entropies.values()) / len(within_task_entropies)
        ),
        "within_task_state_entropies": within_task_entropies,
        "observed_strategy_counts": dict(sorted(strategy_counts.items())),
        "mean_reachability_interval_width": sum(interval_widths) / len(interval_widths),
        "sensitivity_profiles": profiles,
        "scientific_status": "partial",
        "claim_boundary": (
            "The run validates model-visible conditioning and reachability-aware update "
            "mechanics. Two unconditioned attempts per task leave wide uncertainty, and "
            "task-conditioned state IDs are not cross-task behavioral diversity."
        ),
    }
    report["report_hash"] = canonical_hash(
        report,
        prefix="finance_phase1_reachability_analysis:",
    )
    _write_json(experiment_dir / "scientific_analysis.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze reachability uncertainty and Energy sensitivity"
    )
    parser.add_argument("--experiment-dir", required=True)
    parser.add_argument("--artifacts-path", required=True)
    parser.add_argument("--phase1-aggregate-dir", required=True)
    return parser


def main() -> None:
    run(_parser().parse_args())


if __name__ == "__main__":
    main()
