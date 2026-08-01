from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from pathlib import Path

from trusted_synthesis.hashing import canonical_hash

from .beneficiary_shift import run_beneficiary_state_shift_experiment
from .contribution_validation import run_contribution_validation
from .dynamics import run_refinement_dynamics_experiment
from .multistate import (
    FinanceTaskStateArtifact,
    build_finance_multi_state_dataset,
)
from .real_rounds import assemble_real_vtdo_rounds
from .render import (
    write_distribution_figure,
    write_markdown_report,
    write_moving_potential_figure,
    write_moving_potential_table,
    write_phase_figure,
    write_refinement_checkpoint_table,
    write_refinement_dynamics_figure,
    write_refinement_round_table,
    write_synthetic_table,
)
from .schema import (
    RefinementCheckpointTrainingPreflight,
    VTDOExperimentConfig,
    VTDOExperimentManifest,
    VTDOStudentTrainingConfig,
    refinement_checkpoint_training_preflight_hash,
)
from .synthetic import run_synthetic_experiment
from .training import (
    build_refinement_checkpoint_training_arms,
    build_training_experiment_preflight,
    write_refinement_checkpoint_training_arms,
    write_training_arms,
)


def run_vtdo_experiment(config: VTDOExperimentConfig) -> VTDOExperimentManifest:
    """Run the sole paper experiment protocol: state, distribution, then training."""

    output_dir = config.output_dir
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"VTDO experiment output directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, str] = {}
    completed: list[str] = []
    blocked: list[str] = []
    limitations: list[str] = []

    config_path = output_dir / "experiment_config.json"
    _write_json(config_path, config.model_dump(mode="json"))
    artifacts["experiment_config"] = config_path.name
    input_manifest = _build_input_manifest(config)
    input_path = output_dir / "input_manifest.json"
    _write_json(input_path, input_manifest)
    artifacts["input_manifest"] = input_path.name

    synthetic, state_catalogs, phase_rows = run_synthetic_experiment(
        config.synthetic,
        experiment_id=config.experiment_id,
    )
    synthetic_path = output_dir / "synthetic_experiment_report.json"
    _write_json(synthetic_path, synthetic.model_dump(mode="json"))
    artifacts["synthetic_report"] = synthetic_path.name
    states_path = output_dir / "synthetic_states.jsonl"
    states_path.write_text(
        "".join(
            json.dumps({"seed": seed, **state.model_dump(mode="json")}, sort_keys=True) + "\n"
            for seed, states in sorted(state_catalogs.items())
            for state in states
        ),
        encoding="utf-8",
    )
    artifacts["synthetic_states"] = states_path.name
    metrics_path = output_dir / "synthetic_metric_points.csv"
    _write_rows(metrics_path, (item.model_dump(mode="json") for item in synthetic.metric_points))
    artifacts["synthetic_metrics"] = metrics_path.name
    phase_path = output_dir / "synthetic_phase_observations.csv"
    _write_rows(phase_path, phase_rows)
    artifacts["synthetic_phase"] = phase_path.name
    table_path = output_dir / "table1_synthetic_methods.csv"
    write_synthetic_table(synthetic, table_path)
    artifacts["table1"] = table_path.name
    distribution_figure = output_dir / "figure1_distribution_evolution.svg"
    write_distribution_figure(synthetic, distribution_figure)
    artifacts["figure1"] = distribution_figure.name
    phase_figure = output_dir / "figure2_contribution_novelty_phase.svg"
    write_phase_figure(phase_rows, phase_figure)
    artifacts["figure2"] = phase_figure.name
    completed.append("controlled_synthetic_experiment")

    multi_state = None
    task_artifacts: tuple[FinanceTaskStateArtifact, ...] = ()
    if config.multi_state.enabled:
        multi_dir = output_dir / "finance_multi_state"
        multi_state, task_artifacts = build_finance_multi_state_dataset(
            config.multi_state,
            multi_dir,
        )
        artifacts["finance_multi_state_report"] = str(
            Path("finance_multi_state") / "finance_multi_state_report.json"
        )
        artifacts["finance_multi_state_tasks"] = str(
            Path("finance_multi_state") / "finance_multi_state_tasks.jsonl"
        )
        completed.append("real_finance_multi_state_space")
        if multi_state.status != "passed":
            blocked.append("real_finance_multi_state_space")
            limitations.append(
                "The real Finance state pool did not satisfy the frozen 3-5 states per task "
                "contract for every requested task."
            )

    contribution = None
    if config.contribution_validation.enabled:
        contribution = run_contribution_validation(config.contribution_validation)
        contribution_path = output_dir / "contribution_validation_report.json"
        _write_json(contribution_path, contribution.model_dump(mode="json"))
        artifacts["contribution_validation_report"] = contribution_path.name
        if contribution.status == "passed":
            completed.append("empirical_contribution_validation")
        else:
            blocked.append("empirical_contribution_validation")
            limitations.extend(contribution.blockers)

    beneficiary_shift = None
    if config.beneficiary_state_shift.enabled:
        beneficiary_shift = run_beneficiary_state_shift_experiment(
            config.beneficiary_state_shift
        )
        beneficiary_shift_path = output_dir / "beneficiary_state_shift_report.json"
        _write_json(beneficiary_shift_path, beneficiary_shift.model_dump(mode="json"))
        artifacts["beneficiary_state_shift_report"] = beneficiary_shift_path.name
        if beneficiary_shift.status == "passed":
            completed.append("beneficiary_model_state_shift_experiment")
            if beneficiary_shift.model_state_dependence_observed is not True:
                limitations.append(
                    "The controlled M0-to-M1 probe was valid but did not observe a "
                    "Contribution shift above the frozen tolerance."
                )
        else:
            blocked.append("beneficiary_model_state_shift_experiment")
            limitations.extend(beneficiary_shift.blockers)

    effective_refinement_config = config.refinement_dynamics
    if config.refinement_dynamics.real_round_input_path is not None:
        real_round_output = output_dir / "real_rounds" / "vtdo_rounds.jsonl"
        assembly_report, _ = assemble_real_vtdo_rounds(
            config.refinement_dynamics.real_round_input_path,
            real_round_output,
        )
        assembly_report_path = output_dir / "real_round_assembly_report.json"
        _write_json(assembly_report_path, assembly_report.model_dump(mode="json"))
        artifacts["real_round_assembly_report"] = assembly_report_path.name
        if assembly_report.status == "passed":
            artifacts["assembled_real_rounds"] = str(real_round_output.relative_to(output_dir))
            completed.append("real_round_assembly")
            effective_refinement_config = config.refinement_dynamics.model_copy(
                update={
                    "real_round_input_path": None,
                    "real_round_artifact_paths": (real_round_output,),
                }
            )
        else:
            blocked.append("real_round_assembly")
            limitations.extend(assembly_report.blockers)

    refinement_execution = run_refinement_dynamics_experiment(
        effective_refinement_config,
        config.synthetic,
        synthetic,
        state_catalogs,
        phase_rows,
        experiment_id=config.experiment_id,
    )
    refinement = refinement_execution.report
    refinement_path = output_dir / "refinement_dynamics_report.json"
    _write_json(refinement_path, refinement.model_dump(mode="json"))
    artifacts["refinement_dynamics_report"] = refinement_path.name
    for name, rows in (
        ("controlled_refinement_rounds.csv", refinement_execution.controlled_rows),
        (
            "fixed_potential_operator_verification.csv",
            refinement_execution.fixed_potential_rows,
        ),
        ("moving_potential_tracking_rounds.csv", refinement_execution.moving_potential_rows),
        ("real_refinement_rounds.csv", refinement_execution.real_rows),
    ):
        _write_rows(output_dir / name, rows)
        artifacts[name.removesuffix(".csv")] = name
    moving_table = output_dir / "table2_moving_potential_tracking.csv"
    write_moving_potential_table(refinement, moving_table)
    artifacts["table2"] = moving_table.name
    dynamics_table = output_dir / "table3_refinement_dynamics.csv"
    write_refinement_round_table(refinement, dynamics_table)
    artifacts["table3"] = dynamics_table.name
    checkpoint_table = output_dir / "table4_refinement_checkpoints.csv"
    write_refinement_checkpoint_table(refinement, checkpoint_table)
    artifacts["table4"] = checkpoint_table.name
    moving_figure = output_dir / "figure3_moving_potential_tracking.svg"
    write_moving_potential_figure(refinement_execution.moving_potential_rows, moving_figure)
    artifacts["figure3"] = moving_figure.name
    dynamics_figure = output_dir / "figure4_refinement_dynamics.svg"
    write_refinement_dynamics_figure(refinement, dynamics_figure)
    artifacts["figure4"] = dynamics_figure.name
    completed.extend(
        (
            "fixed_potential_update_operator_verification",
            "finite_step_refinement_diagnostics",
        )
    )
    if refinement.practical_stabilization.practical_stabilization_observed:
        completed.append("practical_refinement_stabilization_observed")
    else:
        limitations.append(
            "No controlled seed met the frozen practical-stabilization criterion within "
            "the finite analysis horizon."
        )
    if not refinement.fixed_potential_contraction.projective_contraction_verified:
        blocked.append("fixed_potential_update_operator_verification")
    for track in refinement.moving_potential_tracks:
        component = f"synthetic_moving_potential_tracking:{track.track}"
        if track.status == "passed":
            completed.append(component)
        else:
            blocked.append(component)
    if refinement.real_refinement.status != "passed":
        blocked.append("real_financial_refinement")
        limitations.extend(refinement.real_refinement.blockers)

    training_preflight = None
    checkpoint_training_preflight = None
    if config.training.enabled:
        student = VTDOStudentTrainingConfig.from_json(config.training.training_config_path)
        student_path = output_dir / "student_training_config.json"
        _write_json(student_path, student.model_dump(mode="json"))
        artifacts["student_training_config"] = student_path.name
        training_preflight, arms, benchmark_leakage = build_training_experiment_preflight(
            config.training,
            artifacts=task_artifacts,
            vtdo_round_artifact_paths=effective_refinement_config.real_round_artifact_paths,
            primary_training_round=config.refinement_dynamics.primary_training_round,
        )
        preflight_path = output_dir / "training_preflight.json"
        _write_json(preflight_path, training_preflight.model_dump(mode="json"))
        artifacts["training_preflight"] = preflight_path.name
        benchmark_leakage_path = output_dir / "benchmark_leakage_audit.json"
        _write_json(benchmark_leakage_path, benchmark_leakage.model_dump(mode="json"))
        artifacts["benchmark_leakage_audit"] = benchmark_leakage_path.name
        written = write_training_arms(output_dir / "training_arms", arms)
        artifacts.update(
            {
                f"training_{key}": str(Path("training_arms") / Path(value).name)
                for key, value in written.items()
            }
        )
        completed.append("training_arm_artifact_materialization")
        if not training_preflight.primary_causal_training_ready:
            blocked.append("equal_supervised_token_training")
            limitations.extend(training_preflight.shared_training_blockers)
            limitations.extend(training_preflight.primary_causal_blockers)
        if not training_preflight.full_comparison_matrix_ready:
            blocked.append("full_comparison_matrix")
            limitations.extend(training_preflight.secondary_comparison_blockers)

        training_checkpoint_rounds = tuple(
            sorted({1, config.refinement_dynamics.primary_training_round})
        )
        checkpoint_arms, checkpoint_blockers = build_refinement_checkpoint_training_arms(
            effective_refinement_config.real_round_artifact_paths,
            task_artifacts,
            training_checkpoint_rounds,
        )
        checkpoint_blocker_values = list(checkpoint_blockers)
        if training_preflight.external_benchmark_status != "ready":
            checkpoint_blocker_values.append(
                "external_benchmarks_not_ready_for_checkpoint_comparison"
            )
        records_per_checkpoint: dict[str, int] = {}
        tasks_per_checkpoint: dict[str, int] = {}
        states_per_checkpoint: dict[str, int] = {}
        for round_index, records in sorted(checkpoint_arms.items()):
            key = str(round_index)
            records_per_checkpoint[key] = len(records)
            tasks_per_checkpoint[key] = len({item.task_id for item in records})
            states_per_checkpoint[key] = len(
                {
                    item.trajectory_state_id
                    for item in records
                    if item.trajectory_state_id is not None
                }
            )
            if tasks_per_checkpoint[key] < config.training.minimum_unique_tasks_per_arm:
                checkpoint_blocker_values.append(
                    f"round_{round_index}_unique_tasks_below_minimum:"
                    f"{tasks_per_checkpoint[key]}<"
                    f"{config.training.minimum_unique_tasks_per_arm}"
                )
            if states_per_checkpoint[key] < config.training.minimum_unique_states_per_arm:
                checkpoint_blocker_values.append(
                    f"round_{round_index}_unique_states_below_minimum:"
                    f"{states_per_checkpoint[key]}<"
                    f"{config.training.minimum_unique_states_per_arm}"
                )
        materialized_rounds = tuple(sorted(checkpoint_arms))
        checkpoint_blocker_tuple = tuple(sorted(set(checkpoint_blocker_values)))
        checkpoint_values = {
            "training_config_hash": student.config_hash,
            "supervised_token_budget": config.training.target_supervised_tokens,
            "analysis_checkpoint_rounds": config.refinement_dynamics.checkpoint_rounds,
            "training_checkpoint_rounds": training_checkpoint_rounds,
            "materialized_training_rounds": materialized_rounds,
            "records_per_checkpoint": records_per_checkpoint,
            "unique_tasks_per_checkpoint": tasks_per_checkpoint,
            "unique_states_per_checkpoint": states_per_checkpoint,
            "external_benchmark_status": training_preflight.external_benchmark_status,
            "ready": (
                materialized_rounds == training_checkpoint_rounds
                and training_preflight.external_benchmark_status == "ready"
                and not checkpoint_blocker_tuple
            ),
            "blockers": checkpoint_blocker_tuple,
        }
        provisional_checkpoint = RefinementCheckpointTrainingPreflight.model_construct(
            **checkpoint_values,
            report_hash="pending",
        )
        checkpoint_training_preflight = RefinementCheckpointTrainingPreflight(
            **checkpoint_values,
            report_hash=refinement_checkpoint_training_preflight_hash(provisional_checkpoint),
        )
        checkpoint_preflight_path = output_dir / "refinement_checkpoint_training_preflight.json"
        _write_json(
            checkpoint_preflight_path,
            checkpoint_training_preflight.model_dump(mode="json"),
        )
        artifacts["refinement_checkpoint_training_preflight"] = checkpoint_preflight_path.name
        checkpoint_paths = write_refinement_checkpoint_training_arms(
            output_dir / "refinement_checkpoint_training_arms",
            checkpoint_arms,
        )
        for key, value in checkpoint_paths.items():
            artifacts[f"refinement_checkpoint_{key}"] = str(Path(value).relative_to(output_dir))
        if checkpoint_training_preflight.ready:
            completed.append("one_shot_iterative_checkpoint_training_preflight")
        else:
            blocked.append("one_shot_iterative_checkpoint_training")
            limitations.extend(checkpoint_training_preflight.blockers)

    limitations.extend(
        (
            "Synthetic exact contribution is a controlled estimator test, not a causal "
            "empirical estimate.",
            "The fixed-potential result verifies the update operator only; it is not evidence "
            "that the moving-feedback process converges to a static optimum.",
            "Moving-potential results are reported as instantaneous-optimum tracking, "
            "variational-objective improvement, dynamic regret, and practical stabilization.",
            "Deterministic surface variants are quotient probes only and never expand the "
            "positive training state support.",
        )
    )
    limitations_tuple = tuple(sorted(set(limitations)))
    report_path = output_dir / "vtdo_experiment_report.md"
    write_markdown_report(
        report_path,
        synthetic=synthetic,
        refinement=refinement,
        multi_state=multi_state,
        contribution=contribution,
        beneficiary_shift=beneficiary_shift,
        training=training_preflight,
        checkpoint_training=checkpoint_training_preflight,
        limitations=limitations_tuple,
    )
    artifacts["markdown_report"] = report_path.name

    repo_root = Path(__file__).resolve().parents[4]
    blocked_unique = tuple(sorted(set(blocked)))
    status = (
        "partial" if blocked_unique and completed else "blocked" if blocked_unique else "passed"
    )
    values = {
        "experiment_id": config.experiment_id,
        "config_hash": config.config_hash,
        "synthetic_report_hash": synthetic.artifact_hash,
        "refinement_dynamics_report_hash": refinement.report_hash,
        "multi_state_report_id": multi_state.report_id if multi_state else None,
        "contribution_validation_report_id": contribution.report_id if contribution else None,
        "beneficiary_state_shift_report_id": (
            beneficiary_shift.report_id if beneficiary_shift else None
        ),
        "training_preflight_hash": (training_preflight.report_hash if training_preflight else None),
        "refinement_checkpoint_training_preflight_hash": (
            checkpoint_training_preflight.report_hash if checkpoint_training_preflight else None
        ),
        "input_manifest_hash": input_manifest["manifest_hash"],
        "completed_components": tuple(completed),
        "blocked_components": blocked_unique,
        "artifact_paths": dict(sorted(artifacts.items())),
        "git_commit": _git(repo_root, ("rev-parse", "HEAD"), fallback="unknown"),
        "git_worktree_dirty": bool(_git(repo_root, ("status", "--porcelain"), fallback="unknown")),
        "status": status,
        "limitations": limitations_tuple,
    }
    manifest = VTDOExperimentManifest(
        **values,
        manifest_hash=canonical_hash(values, prefix="vtdo_experiment_manifest:"),
    )
    _write_json(output_dir / "manifest.json", manifest.model_dump(mode="json"))
    return manifest


def _write_rows(path: Path, rows) -> None:
    values = tuple(rows)
    if not values:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=tuple(values[0]))
        writer.writeheader()
        writer.writerows(values)


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _build_input_manifest(config: VTDOExperimentConfig) -> dict[str, object]:
    entries: list[dict[str, object]] = []
    repo_root = Path(__file__).resolve().parents[4]

    def add_source(role: str, path: Path) -> None:
        if path.is_dir():
            files = tuple(sorted(item for item in path.glob("*.json*") if item.is_file()))
            if not files:
                entries.append({"role": role, "path": str(path), "status": "missing"})
                return
            directory_values = {
                item.name: {"size_bytes": item.stat().st_size, "sha256": _sha256(item)}
                for item in files
            }
            entries.append(
                {
                    "role": role,
                    "path": str(path.resolve()),
                    "status": "present",
                    "source_type": "directory",
                    "file_count": len(files),
                    "content_hash": canonical_hash(
                        directory_values,
                        prefix="vtdo_round_directory:",
                    ),
                }
            )
            return
        if not path.is_file():
            entries.append({"role": role, "path": str(path), "status": "missing"})
            return
        entries.append(
            {
                "role": role,
                "path": str(path.resolve()),
                "status": "present",
                "source_type": "file",
                "size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )

    add_source("finance_archive_config", config.multi_state.finance_archive_config_path)
    add_source("student_training_config", config.training.training_config_path)
    if config.training.ccgr_task_distribution_path is not None:
        add_source("ccgr_task_distribution", config.training.ccgr_task_distribution_path)
    if config.contribution_validation.observation_path is not None:
        add_source(
            "contribution_validation_observations",
            config.contribution_validation.observation_path,
        )
    if config.beneficiary_state_shift.baseline_observation_path is not None:
        add_source(
            "beneficiary_shift_baseline_observations",
            config.beneficiary_state_shift.baseline_observation_path,
        )
    if config.beneficiary_state_shift.updated_observation_path is not None:
        add_source(
            "beneficiary_shift_updated_observations",
            config.beneficiary_state_shift.updated_observation_path,
        )
    if config.refinement_dynamics.real_round_input_path is not None:
        add_source("real_vtdo_round_input", config.refinement_dynamics.real_round_input_path)
    for snapshot in config.training.external_benchmarks:
        add_source(f"external_benchmark:{snapshot.benchmark_id}", snapshot.path)
    for index, path in enumerate(config.refinement_dynamics.real_round_artifact_paths):
        add_source(f"real_vtdo_round:{index}", path)
    values: dict[str, object] = {
        "experiment_config_hash": config.config_hash,
        "source_tree_hash": _source_tree_hash(repo_root),
        "entries": entries,
    }
    return {**values, "manifest_hash": canonical_hash(values, prefix="vtdo_input_manifest:")}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_tree_hash(repo_root: Path) -> str:
    files = [repo_root / "pyproject.toml"]
    for root in (repo_root / "src" / "trusted_synthesis", repo_root / "tests"):
        files.extend(sorted(root.rglob("*.py")))
    payload = {str(path.relative_to(repo_root)): _sha256(path) for path in files if path.is_file()}
    return canonical_hash(payload, prefix="vtdo_execution_source_tree:")


def _git(repo_root: Path, arguments: tuple[str, ...], *, fallback: str) -> str:
    try:
        return subprocess.check_output(
            ("git", *arguments),
            cwd=repo_root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return fallback
