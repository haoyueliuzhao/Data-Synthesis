from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import json
import math
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from trusted_synthesis.core.evaluation.contracts import (
    QualityContractCompiler,
    QualityContractRuntime,
)
from trusted_synthesis.core.operations.registry import default_registry
from trusted_synthesis.core.trajectory import TrajectoryValidityEvaluator
from trusted_synthesis.core.trajectory.candidate_verifier import CandidateWorkflowVerifier
from trusted_synthesis.core.trajectory.schema import ActionType, Trajectory, TrajectoryStep
from trusted_synthesis.core.trajectory.state import TrajectoryStateAssignment
from trusted_synthesis.core.trajectory.validity import TrajectoryValidityReport
from trusted_synthesis.core.vtdo import (
    AnchoredEnergyConfig,
    ContributionProductionAuthorization,
    ProbeAdaptationResult,
    StateConditionedExplorationBatch,
    ValidityThresholds,
    ValidTrajectoryStateMaterializer,
    empty_optimizer_state_hash,
    estimate_contributions_from_probes,
    estimate_pushforward_distribution,
    estimate_state_validity,
    make_contribution_data_isolation_contract,
    make_contribution_metric_contract,
    make_contribution_probe_observation,
    make_contribution_probe_protocol,
    make_probe_optimizer_contract,
    make_trajectory_state_catalog,
    make_uniform_coverage_prior,
    make_vtdo_role_contract,
    update_valid_trajectory_distribution,
)
from trusted_synthesis.domains.finance.adapter import FinanceArchiveAdapter
from trusted_synthesis.domains.finance.policy import FinanceSemanticPolicy
from trusted_synthesis.domains.finance.quality_clauses import FinanceQualityClauseProvider
from trusted_synthesis.domains.finance.schema import FinanceArchiveConfig
from trusted_synthesis.domains.finance.verification import FinanceClaimVerifier
from trusted_synthesis.experiments.vtdo_experiment.multistate import AcceptedFinanceState
from trusted_synthesis.experiments.vtdo_experiment.phase1_probe_gpu import (
    PHASE1_VERSION,
    _load_target_artifact,
    _read_json,
    _selected_states,
    _write_json,
    prepare_probe,
    run_probe_worker,
    train_baseline,
)
from trusted_synthesis.experiments.vtdo_experiment.training import _make_record
from trusted_synthesis.hashing import canonical_hash


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _freeze_input_manifest(paths: dict[str, Path]) -> dict[str, Any]:
    files = {
        name: {
            "path": str(path.resolve()),
            "size": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for name, path in sorted(paths.items())
    }
    value: dict[str, Any] = {
        "experiment_version": PHASE1_VERSION,
        "files": files,
    }
    value["manifest_hash"] = canonical_hash(
        value,
        prefix="finance_phase1_input_manifest:",
    )
    return value


def _subcatalog(artifact, states: tuple[AcceptedFinanceState, ...]):
    public_conditions = {
        state.assignment.assignment_id: artifact.state_catalog.public_state_conditions[
            state.assignment.state.state_id
        ]
        for state in states
    }
    return make_trajectory_state_catalog(
        ((state.assignment, state.validity_report, state.trajectory) for state in states),
        state_space_compilation=artifact.state_space_compilation,
        discovery_method="verified_finance_fixture_seed_for_phase1",
        revision_reason="phase1_three_state_probe_support",
        public_conditions_by_assignment_id=public_conditions,
        parent_catalog_id=artifact.state_catalog.catalog_id,
    )


def _load_real_pushforward(
    path: Path,
    selected_state_ids: set[str],
) -> tuple[tuple[TrajectoryStateAssignment, ...], tuple[TrajectoryValidityReport, ...]]:
    assignments: list[TrajectoryStateAssignment] = []
    reports: list[TrajectoryValidityReport] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        report = TrajectoryValidityReport.model_validate(record["validity_report"])
        assignment = TrajectoryStateAssignment.model_validate(record["state_assignment"])
        if report.valid and assignment.state.state_id in selected_state_ids:
            assignments.append(assignment)
            reports.append(report)
    return tuple(assignments), tuple(reports)


def _validity_estimates(
    states: tuple[AcceptedFinanceState, ...],
    replicate_path: Path,
    conditioned_batch_path: Path,
):
    assignments_by_state: dict[str, list[TrajectoryStateAssignment]] = defaultdict(list)
    reports_by_state: dict[str, list[TrajectoryValidityReport]] = defaultdict(list)
    for state in states:
        state_id = state.assignment.state.state_id
        assignments_by_state[state_id].append(state.assignment)
        reports_by_state[state_id].append(state.validity_report)
    real_assignments, real_reports = _load_real_pushforward(
        replicate_path,
        set(assignments_by_state),
    )
    real_report_by_id = {item.trajectory_id: item for item in real_reports}
    for assignment in real_assignments:
        state_id = assignment.state.state_id
        assignments_by_state[state_id].append(assignment)
        reports_by_state[state_id].append(real_report_by_id[assignment.trajectory_id])
    conditioned = StateConditionedExplorationBatch.model_validate_json(
        conditioned_batch_path.read_text(encoding="utf-8")
    )
    for observation in conditioned.observations:
        if observation.assignment is None:
            continue
        state_id = observation.assignment.state.state_id
        if state_id not in assignments_by_state:
            continue
        assignments_by_state[state_id].append(observation.assignment)
        reports_by_state[state_id].append(observation.validity_report)
    thresholds = ValidityThresholds(reject_below=0.5, accept_at_or_above=0.9)
    return tuple(
        estimate_state_validity(
            assignments_by_state[state_id],
            reports_by_state[state_id],
            thresholds=thresholds,
        )
        for state_id in sorted(assignments_by_state)
    )


def _make_evaluator(archive_config_path: Path) -> TrajectoryValidityEvaluator:
    adapter = FinanceArchiveAdapter(FinanceArchiveConfig.from_json(archive_config_path))
    registry = default_registry()
    verifier = CandidateWorkflowVerifier(
        registry,
        semantic_policy=FinanceSemanticPolicy(),
        claim_verifier=FinanceClaimVerifier(),
        source_grounding_verifier=adapter.source_grounding_verifier(),
    )
    compiler = QualityContractCompiler(
        registry,
        domain_provider=FinanceQualityClauseProvider(),
    )
    return TrajectoryValidityEvaluator(
        verifier,
        contract_runtime=QualityContractRuntime(
            verifier,
            verifier_registry=compiler.verifier_registry,
        ),
    )


class Phase1DeterministicMaterializer:
    provider_id = "finance_phase1_deterministic_materializer"
    provider_version = "1.0.0"

    def __init__(self, states: Iterable[AcceptedFinanceState], catalog) -> None:
        state_by_id = {item.assignment.state.state_id: item for item in states}
        self._by_condition = {
            catalog.public_state_conditions[state_id].condition_id: state
            for state_id, state in state_by_id.items()
        }

    def generate(self, request) -> Iterable[Trajectory]:
        source = self._by_condition[request.state_condition.condition_id]
        for index in range(request.candidate_count):
            nonce = canonical_hash(
                {
                    "request_id": request.request_id,
                    "candidate_index": index,
                    "seed": request.seed,
                },
                prefix="phase1_materialization_nonce:",
            )
            steps: list[TrajectoryStep] = []
            for step in source.trajectory.steps:
                if step.action == ActionType.PLAN:
                    tool_input = {**step.tool_input, "materialization_nonce": nonce}
                    step = step.model_copy(update={"tool_input": tool_input})
                steps.append(step)
            trajectory_id = canonical_hash(
                {
                    "source_trajectory_id": source.trajectory.trajectory_id,
                    "nonce": nonce,
                },
                prefix="finance_phase1_materialized_trajectory:",
            )
            yield source.trajectory.model_copy(
                update={
                    "trajectory_id": trajectory_id,
                    "steps": tuple(steps),
                    "generator_version": "finance_phase1_materializer.v1",
                }
            )


def _write_cn_svg(path: Path, rows: list[dict[str, Any]]) -> None:
    width, height = 760, 420
    margin = 70
    inner_width = width - 2 * margin
    inner_height = height - 2 * margin
    maximum_delta = max(
        (abs(float(item["probability_delta"])) for item in rows),
        default=1.0,
    )
    if math.isclose(maximum_delta, 0.0):
        maximum_delta = 1.0

    circles = []
    for row in rows:
        x = margin + float(row["normalized_novelty"]) * inner_width
        y = height - margin - float(row["normalized_contribution"]) * inner_height
        label = str(row["strategy"])
        delta = float(row["probability_delta"])
        color = "#2ca02c" if delta >= 0 else "#d62728"
        opacity = 0.35 + 0.65 * abs(delta) / maximum_delta
        circles.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="8" fill="{color}" '
            f'fill-opacity="{opacity:.3f}"><title>delta_pi={delta:.6f}</title></circle>'
            f'<text x="{x + 11:.1f}" y="{y - 9:.1f}" font-size="12">{label}</text>'
        )
    horizontal_axis = (
        f'<line x1="{margin}" y1="{height - margin}" '
        f'x2="{width - margin}" y2="{height - margin}" stroke="#333"/>'
    )
    vertical_axis = (
        f'<line x1="{margin}" y1="{margin}" x2="{margin}" y2="{height - margin}" stroke="#333"/>'
    )
    horizontal_label = (
        f'<text x="{width / 2}" y="{height - 20}" '
        'text-anchor="middle" font-size="14">Normalized novelty</text>'
    )
    vertical_label = (
        f'<text x="20" y="{height / 2}" '
        f'transform="rotate(-90 20 {height / 2})" '
        'text-anchor="middle" font-size="14">'
        "Normalized contribution</text>"
    )
    svg = "\n".join(
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
            '<rect width="100%" height="100%" fill="white"/>',
            horizontal_axis,
            vertical_axis,
            horizontal_label,
            vertical_label,
            "".join(circles),
            "</svg>",
        )
    )
    path.write_text(svg + "\n", encoding="utf-8")


def _total_variation(left: dict[str, float], right: dict[str, float]) -> float:
    if set(left) != set(right):
        raise ValueError("distribution supports differ")
    return 0.5 * sum(abs(left[key] - right[key]) for key in left)


def _jensen_shannon(left: dict[str, float], right: dict[str, float]) -> float:
    if set(left) != set(right):
        raise ValueError("distribution supports differ")
    midpoint = {key: 0.5 * (left[key] + right[key]) for key in left}

    def kl(source: dict[str, float]) -> float:
        return sum(source[key] * math.log(source[key] / midpoint[key]) for key in source)

    return 0.5 * kl(left) + 0.5 * kl(right)


def _energy_sensitivity(
    pi0, coverage, validity, contribution, authorization, roles
):
    profiles = (
        ("default", 0.5, 0.5, 1.0, 1.0, 1.0),
        ("contribution_heavy", 0.75, 0.25, 1.0, 1.0, 1.0),
        ("history_heavy", 0.5, 0.5, 4.0, 1.0, 1.0),
        ("conservative", 0.75, 0.25, 4.0, 1.0, 1.0),
        ("higher_novelty_temperature", 0.5, 0.5, 1.0, 1.0, 2.0),
    )
    rows = []
    for name, contribution_weight, novelty_weight, history, anchor, novelty_temp in profiles:
        config = AnchoredEnergyConfig(
            epsilon=1e-6,
            contribution_temperature=0.01,
            novelty_temperature=novelty_temp,
            contribution_weight=contribution_weight,
            novelty_weight=novelty_weight,
            history_kl_weight=history,
            coverage_kl_weight=anchor,
        )
        candidate = update_valid_trajectory_distribution(
            pi0,
            coverage,
            validity,
            contribution,
            authorization,
            config,
            roles,
        )
        rows.append(
            {
                "profile": name,
                "config": config.model_dump(mode="json"),
                "update_id": candidate.update_id,
                "probabilities": candidate.next_distribution.probabilities,
                "total_variation": candidate.total_variation_from_history,
                "kl_to_history": candidate.kl_to_history,
                "js_to_history": _jensen_shannon(
                    pi0.probabilities,
                    candidate.next_distribution.probabilities,
                ),
                "next_entropy": candidate.next_entropy,
            }
        )
    return rows


def aggregate_phase1(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "probe_plan.json")
    baseline = _read_json(output_dir / "beneficiary_training_report.json")
    authorization_path = Path(args.contribution_authorization_path).resolve()
    authorization = ContributionProductionAuthorization.model_validate(
        _read_json(authorization_path)
    )
    artifact = _load_target_artifact(Path(plan["artifacts_path"]), str(plan["task_id"]))
    states = _selected_states(artifact)
    catalog = _subcatalog(artifact, states)
    state_ids = {item.assignment.state.state_id for item in states}
    coverage = make_uniform_coverage_prior(catalog.task_condition_id, state_ids)
    real_assignments, _ = _load_real_pushforward(
        Path(args.replicates_path).resolve(),
        state_ids,
    )
    pi0_estimate = estimate_pushforward_distribution(
        real_assignments,
        coverage,
        round_index=0,
        prior_strength=1.0,
    )
    pi0 = pi0_estimate.distribution

    update_ids = {
        state_id: (str(value["record_id"]),)
        for state_id, value in plan["probe_update_records_by_state"].items()
    }
    isolation = make_contribution_data_isolation_contract(
        task_condition_id=catalog.task_condition_id,
        baseline_training_set_id=canonical_hash(
            plan["baseline_record_ids"], prefix="phase1_baseline_training_set:"
        ),
        baseline_training_instance_ids=plan["baseline_record_ids"],
        probe_update_instance_ids_by_state=update_ids,
        internal_validation_set_id=canonical_hash(
            plan["internal_validation_record_ids"],
            prefix="phase1_internal_validation_set:",
        ),
        internal_validation_instance_ids=plan["internal_validation_record_ids"],
        final_test_set_id=canonical_hash(
            plan["final_test_record_ids"], prefix="phase1_untouched_final_test_set:"
        ),
        final_test_instance_ids=plan["final_test_record_ids"],
    )
    metric = make_contribution_metric_contract(
        target_metric_id="negative_supervised_token_nll",
        evaluation_distribution_id=isolation.internal_validation_set_id,
        evaluation_snapshot_hash=canonical_hash(
            plan["internal_validation_record_ids"],
            prefix="phase1_validation_snapshot:",
        ),
        score_transform="negative_loss",
    )
    optimizer = make_probe_optimizer_contract(
        optimizer_name="sgd",
        learning_rate=float(plan["learning_rate"]),
        step_count=int(plan["probe_step_count"]),
        weight_decay=0.0,
        momentum=0.0,
    )
    protocol = make_contribution_probe_protocol(
        beneficiary_model_state_id=str(baseline["model_state_id"]),
        beneficiary_checkpoint_hash=str(baseline["checkpoint_hash"]),
        metric_contract=metric,
        data_isolation=isolation,
        optimizer=optimizer,
        probe_seeds=plan["probe_seeds"],
        uncertainty_penalty_coefficient=float(plan["probe_uncertainty_penalty_coefficient"]),
    )
    worker_dir = output_dir / "probe_workers"
    observations = []
    worker_reports = []
    baseline_performance = float(baseline["validation_performance"])
    for state_id in sorted(state_ids):
        for seed in sorted(plan["probe_seeds"]):
            path = worker_dir / f"{state_id.rsplit(':', 1)[-1]}_{seed}.json"
            worker = _read_json(path)
            worker_reports.append(worker)
            if (
                worker["plan_hash"] != plan["plan_hash"]
                or worker["beneficiary_report_hash"] != baseline["report_hash"]
                or worker["state_id"] != state_id
                or int(worker["seed"]) != seed
            ):
                raise ValueError(f"Probe worker crossed a frozen identity: {path}")
            adaptation = ProbeAdaptationResult(
                adapted_model_state_id=str(worker["adapted_model_state_id"]),
                adapted_checkpoint_hash=str(worker["adapted_checkpoint_hash"]),
                base_model_state_id=str(baseline["model_state_id"]),
                base_checkpoint_hash=str(baseline["checkpoint_hash"]),
                optimizer_contract_id=optimizer.contract_id,
                initial_optimizer_state_hash=empty_optimizer_state_hash(optimizer),
                executed_step_count=optimizer.step_count,
            )
            observations.append(
                make_contribution_probe_observation(
                    task_condition_id=catalog.task_condition_id,
                    round_index=0,
                    state_id=state_id,
                    protocol=protocol,
                    seed=seed,
                    adaptation_result=adaptation,
                    baseline_performance=baseline_performance,
                    adapted_performance=float(worker["adapted_performance"]),
                )
            )
    contribution = estimate_contributions_from_probes(pi0, observations)
    validity = _validity_estimates(
        states,
        Path(args.replicates_path).resolve(),
        Path(args.conditioned_batch_path).resolve(),
    )
    roles = make_vtdo_role_contract(
        explorer_provider_id="deepseek_v4_pro_state_conditioned.phase1",
        materialization_provider_id=Phase1DeterministicMaterializer.provider_id,
        beneficiary_model_state_id=str(baseline["model_state_id"]),
        final_student_model_id="qwen2.5-7b-final-student.phase1.not_trained",
    )
    energy_config = AnchoredEnergyConfig(
        epsilon=1e-6,
        contribution_temperature=0.01,
        novelty_temperature=1.0,
        contribution_weight=0.5,
        novelty_weight=0.5,
        history_kl_weight=1.0,
        coverage_kl_weight=1.0,
    )
    update = update_valid_trajectory_distribution(
        pi0,
        coverage,
        validity,
        contribution,
        authorization,
        energy_config,
        roles,
    )
    sensitivity = _energy_sensitivity(
        pi0,
        coverage,
        validity,
        contribution,
        authorization,
        roles,
    )

    evaluator = _make_evaluator(Path(args.archive_config_path).resolve())
    materializer_provider = Phase1DeterministicMaterializer(states, catalog)
    materialized, materialization_report = ValidTrajectoryStateMaterializer(
        materializer_provider, evaluator
    ).materialize(
        artifact.omega,
        catalog,
        update.next_distribution,
        roles,
        total_budget=args.materialization_budget,
        seed=20260803,
        maximum_attempt_multiplier=2,
    )
    strategy_by_state = {item.assignment.state.state_id: item.strategy for item in states}
    training_records = tuple(
        _make_record(
            artifact=artifact,
            trajectory=item.trajectory,
            state_id=item.target_state.state_id,
            arm_id="B5_vtdo",
            accepted_target=True,
            sampling_weight=update.next_distribution.probabilities[item.target_state.state_id],
            source_distribution_id=update.next_distribution.distribution_id,
            source_artifact_id=item.artifact_id,
            metadata={
                "lineage_strategy": strategy_by_state[item.target_state.state_id],
                "materialization_artifact_id": item.artifact_id,
                "phase1_controlled_materializer": True,
            },
        )
        for item in materialized
    )

    aggregate_dir = output_dir / "distribution_update"
    aggregate_dir.mkdir(parents=True, exist_ok=True)
    input_paths = {
        "probe_plan": output_dir / "probe_plan.json",
        "beneficiary_training_report": output_dir / "beneficiary_training_report.json",
        "explorer_replicates": Path(args.replicates_path).resolve(),
        "state_conditioned_explorer_batch": Path(args.conditioned_batch_path).resolve(),
        "archive_config": Path(args.archive_config_path).resolve(),
        "contribution_production_authorization": authorization_path,
        "multi_state_artifacts": Path(plan["artifacts_path"]).resolve(),
        "multi_state_report": Path(plan["artifacts_path"]).resolve().parent
        / "finance_multi_state_report.json",
    }
    for index, path in enumerate(sorted(worker_dir.glob("*.json"))):
        input_paths[f"probe_worker_{index:02d}"] = path
    input_manifest = _freeze_input_manifest(input_paths)
    _write_json(aggregate_dir / "phase1_input_manifest.json", input_manifest)
    (aggregate_dir / "probe_observations.jsonl").write_text(
        "".join(item.model_dump_json() + "\n" for item in observations),
        encoding="utf-8",
    )
    (aggregate_dir / "materialized_artifacts.jsonl").write_text(
        "".join(item.model_dump_json() + "\n" for item in materialized),
        encoding="utf-8",
    )
    (aggregate_dir / "D1_materialized_training_records.jsonl").write_text(
        "".join(item.model_dump_json() + "\n" for item in training_records),
        encoding="utf-8",
    )
    for name, value in (
        ("three_state_catalog.json", catalog),
        ("pi0_empirical_estimate.json", pi0_estimate),
        ("coverage_prior.json", coverage),
        ("contribution_protocol.json", protocol),
        ("contribution_manifest.json", contribution),
        ("contribution_production_authorization.json", authorization),
        ("anchored_distribution_update.json", update),
        ("materialization_report.json", materialization_report),
    ):
        (aggregate_dir / name).write_text(value.model_dump_json(indent=2) + "\n", encoding="utf-8")

    estimates = {item.state_id: item for item in contribution.estimates}
    potentials = {item.state_id: item for item in update.state_potentials}
    rows: list[dict[str, Any]] = []
    for state_id in sorted(state_ids):
        worker_values = [
            float(item["performance_gain"])
            for item in worker_reports
            if item["state_id"] == state_id
        ]
        rows.append(
            {
                "state_id": state_id,
                "strategy": strategy_by_state[state_id],
                "pi0_probability": pi0.probabilities[state_id],
                "pi1_probability": update.next_distribution.probabilities[state_id],
                "raw_contribution": estimates[state_id].raw_marginal_gain,
                "centered_contribution": estimates[state_id].centered_contribution,
                "contribution_standard_error": estimates[state_id].standard_error,
                "seed_gains": worker_values,
                "coverage_relative_novelty": potentials[state_id].coverage_relative_novelty,
                "normalized_contribution": potentials[state_id].normalized_contribution,
                "normalized_novelty": potentials[state_id].normalized_novelty,
                "potential": potentials[state_id].potential,
                "probability_delta": (
                    update.next_distribution.probabilities[state_id] - pi0.probabilities[state_id]
                ),
                "validity_observation_count": next(
                    item.attempted_trajectory_count
                    for item in validity
                    if item.state_id == state_id
                ),
            }
        )
    csv_path = aggregate_dir / "contribution_novelty_states.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as sink:
        writer = csv.DictWriter(sink, fieldnames=tuple(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    _write_cn_svg(aggregate_dir / "contribution_novelty_states.svg", rows)
    _write_json(
        aggregate_dir / "energy_sensitivity.json",
        {"profiles": sensitivity},
    )

    real_observed_states = {assignment.state.state_id for assignment in real_assignments}
    conditioned = StateConditionedExplorationBatch.model_validate_json(
        Path(args.conditioned_batch_path).read_text(encoding="utf-8")
    )
    real_observed_states.update(
        observation.assignment.state.state_id
        for observation in conditioned.observations
        if observation.assignment is not None
        and observation.validity_report.valid
        and observation.assignment.state.state_id in state_ids
    )
    multi_state_report = _read_json(
        Path(plan["artifacts_path"]).parent / "finance_multi_state_report.json"
    )
    replicate_attempt_count = sum(
        bool(line.strip())
        for line in Path(args.replicates_path).read_text(encoding="utf-8").splitlines()
    )
    source_to_release_tv = _total_variation(
        update.next_distribution.probabilities,
        materialization_report.released_state_distribution,
    )
    source_to_release_js = _jensen_shannon(
        update.next_distribution.probabilities,
        materialization_report.released_state_distribution,
    )
    failure_counts = materialization_report.failure_counts
    attempted = materialization_report.attempted_trajectory_count
    invalid_count = failure_counts.get("invalid_trajectory", 0)
    verification_errors = failure_counts.get("verification_error", 0)
    off_target_count = sum(materialization_report.off_target_state_counts.values())
    validity_rate = (
        (attempted - invalid_count - verification_errors) / attempted if attempted else 0.0
    )
    state_hit_rate = (
        (attempted - invalid_count - verification_errors - off_target_count) / attempted
        if attempted
        else 0.0
    )
    summary = {
        "experiment_version": PHASE1_VERSION,
        "input_manifest_hash": input_manifest["manifest_hash"],
        "status": "partial" if len(real_observed_states) < 3 else "passed",
        "task_id": artifact.omega.task.task_id,
        "task_instruction": artifact.omega.task.public.instruction,
        "real_data_source": "legacy_raw_financial_data_lake_pinned_kg",
        "compiled_task_count": multi_state_report["accepted_task_count"],
        "compiled_tasks_with_three_or_more_states": multi_state_report[
            "tasks_with_three_or_more_states"
        ],
        "q1_compiled_state_space_passed": (
            multi_state_report["accepted_task_count"] == 100
            and multi_state_report["tasks_with_three_or_more_states"] == 100
        ),
        "compiled_accepted_state_count_for_probe_task": len(state_ids),
        "real_unconditioned_explorer_task_count": 1,
        "real_unconditioned_explorer_attempt_count": replicate_attempt_count,
        "real_unconditioned_explorer_valid_count": len(real_assignments),
        "planned_unconditioned_explorer_attempt_count": 1000,
        "real_unconditioned_explorer_plan_coverage_rate": (replicate_attempt_count / 1000),
        "real_model_observed_accepted_state_count": len(real_observed_states),
        "real_model_observed_state_ids": sorted(real_observed_states),
        "q1_three_real_states_passed": len(real_observed_states) >= 3,
        "q2_distribution_changed": update.total_variation_from_history > 0,
        "q3_contribution_update_closed": True,
        "contribution_production_authorization_id": authorization.authorization_id,
        "contribution_analysis_report_hash": authorization.analysis_report_hash,
        "contribution_probe_task_count": 1,
        "pi0": pi0.probabilities,
        "pi1": update.next_distribution.probabilities,
        "distribution_total_variation": update.total_variation_from_history,
        "kl_pi1_to_pi0": update.kl_to_history,
        "js_pi1_to_pi0": _jensen_shannon(
            pi0.probabilities,
            update.next_distribution.probabilities,
        ),
        "prior_entropy": update.prior_entropy,
        "next_entropy": update.next_entropy,
        "accepted_support_size": len(state_ids),
        "contribution_state_rows": rows,
        "energy_sensitivity": sensitivity,
        "default_energy_profile_production_ready": False,
        "energy_sensitivity_warning": (
            "The default profile makes a large novelty-driven update; select production "
            "hyperparameters only after multi-task sensitivity and downstream validation."
        ),
        "probe_observation_count": len(observations),
        "probe_seed_count": len(plan["probe_seeds"]),
        "materialization_budget": args.materialization_budget,
        "materialization_status": materialization_report.status,
        "materialization_quota_fill_rate": materialization_report.quota_fill_rate,
        "materialization_tv_to_allocated_integer_target": (
            materialization_report.distribution_total_variation
        ),
        "materialization_tv_to_source_pi1": source_to_release_tv,
        "materialization_js_to_source_pi1": source_to_release_js,
        "materialization_state_hit_rate": state_hit_rate,
        "materialization_validity_rate": validity_rate,
        "materialization_end_to_end_acceptance_rate": (
            materialization_report.generation_acceptance_rate
        ),
        "materialization_unique_decision_trace_count": (
            materialization_report.unique_decision_trace_count
        ),
        "controlled_materializer_limitation": (
            "D1 uses independently regenerated deterministic verified trajectories; it does "
            "not establish LLM state-conditioned materialization reliability."
        ),
        "untouched_final_test_record_ids": plan["final_test_record_ids"],
        "untouched_final_test_used_for_selection": False,
        "gpu_probe_worker_count": len(worker_reports),
        "gpu_probe_total_runtime_seconds": sum(
            float(item["runtime_seconds"]) for item in worker_reports
        ),
        "gpu_probe_max_peak_memory_bytes": max(
            int(item["peak_gpu_memory_bytes"]) for item in worker_reports
        ),
    }
    summary["report_hash"] = canonical_hash(summary, prefix="finance_phase1_mvp:")
    _write_json(output_dir / "finance_phase1_mvp_summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the finance VTDO phase-one MVP")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--artifacts-path", required=True)
    prepare.add_argument("--model-dir", required=True)
    prepare.add_argument("--task-id", required=True)
    prepare.add_argument("--output-dir", required=True)
    prepare.set_defaults(handler=prepare_probe)

    baseline = subparsers.add_parser("baseline")
    baseline.add_argument("--output-dir", required=True)
    baseline.set_defaults(handler=train_baseline)

    worker = subparsers.add_parser("probe-worker")
    worker.add_argument("--output-dir", required=True)
    worker.add_argument("--state-id", required=True)
    worker.add_argument("--seed", type=int, required=True)
    worker.set_defaults(handler=run_probe_worker)

    aggregate = subparsers.add_parser("aggregate")
    aggregate.add_argument("--output-dir", required=True)
    aggregate.add_argument("--replicates-path", required=True)
    aggregate.add_argument("--conditioned-batch-path", required=True)
    aggregate.add_argument("--archive-config-path", required=True)
    aggregate.add_argument("--contribution-authorization-path", required=True)
    aggregate.add_argument("--materialization-budget", type=int, default=30)
    aggregate.set_defaults(handler=aggregate_phase1)
    return parser


def main() -> None:
    args = _parser().parse_args()
    args.handler(args)
    gc.collect()


if __name__ == "__main__":
    main()
