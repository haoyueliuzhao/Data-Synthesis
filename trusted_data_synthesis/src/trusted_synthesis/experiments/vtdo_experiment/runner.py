from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from pathlib import Path

from trusted_synthesis.hashing import canonical_hash

from .contribution_validation import run_contribution_validation
from .dynamics import run_refinement_dynamics_experiment
from .multistate import (
    FinanceTaskStateArtifact,
    build_finance_multi_state_dataset,
)
from .render import (
    write_distribution_figure,
    write_markdown_report,
    write_phase_figure,
    write_refinement_checkpoint_table,
    write_refinement_dynamics_figure,
    write_refinement_round_table,
    write_synthetic_table,
)
from .schema import (
    VTDOExperimentConfig,
    VTDOExperimentManifest,
    VTDOStudentTrainingConfig,
)
from .synthetic import run_synthetic_experiment
from .training import build_training_experiment_preflight, write_training_arms


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

    refinement_execution = run_refinement_dynamics_experiment(
        config.refinement_dynamics,
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
        ("fixed_potential_contraction_rounds.csv", refinement_execution.fixed_potential_rows),
        ("real_refinement_rounds.csv", refinement_execution.real_rows),
    ):
        _write_rows(output_dir / name, rows)
        artifacts[name.removesuffix(".csv")] = name
    dynamics_table = output_dir / "table2_refinement_dynamics.csv"
    write_refinement_round_table(refinement, dynamics_table)
    artifacts["table2"] = dynamics_table.name
    checkpoint_table = output_dir / "table3_one_shot_vs_iterative.csv"
    write_refinement_checkpoint_table(refinement, checkpoint_table)
    artifacts["table3"] = checkpoint_table.name
    dynamics_figure = output_dir / "figure3_refinement_dynamics.svg"
    write_refinement_dynamics_figure(refinement, dynamics_figure)
    artifacts["figure3"] = dynamics_figure.name
    completed.extend(("fixed_potential_control", "finite_step_refinement_dynamics"))
    if not refinement.fixed_potential_contraction.projective_contraction_verified:
        blocked.append("fixed_potential_control")
    if refinement.real_refinement.status != "passed":
        blocked.append("real_financial_refinement")
        limitations.extend(refinement.real_refinement.blockers)

    training_preflight = None
    if config.training.enabled:
        student = VTDOStudentTrainingConfig.from_json(config.training.training_config_path)
        student_path = output_dir / "student_training_config.json"
        _write_json(student_path, student.model_dump(mode="json"))
        artifacts["student_training_config"] = student_path.name
        training_preflight, arms = build_training_experiment_preflight(
            config.training,
            artifacts=task_artifacts,
            vtdo_round_artifact_paths=config.refinement_dynamics.real_round_artifact_paths,
        )
        preflight_path = output_dir / "training_preflight.json"
        _write_json(preflight_path, training_preflight.model_dump(mode="json"))
        artifacts["training_preflight"] = preflight_path.name
        written = write_training_arms(output_dir / "training_arms", arms)
        artifacts.update(
            {
                f"training_{key}": str(Path("training_arms") / Path(value).name)
                for key, value in written.items()
            }
        )
        completed.append("b1_b5_training_arm_materialization")
        if not training_preflight.formal_training_ready:
            blocked.append("b1_b5_equal_token_training")
            limitations.extend(training_preflight.blockers)

    limitations.extend(
        (
            "Synthetic exact contribution is a controlled estimator test, not a causal "
            "empirical estimate.",
            "Strict convergence is asserted only in the fixed-potential control. Moving-"
            "potential rounds are described as finite-step practical stabilization.",
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
        training=training_preflight,
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
        "training_preflight_hash": (training_preflight.report_hash if training_preflight else None),
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

    def add_file(role: str, path: Path) -> None:
        if not path.is_file():
            entries.append({"role": role, "path": str(path), "status": "missing"})
            return
        entries.append(
            {
                "role": role,
                "path": str(path.resolve()),
                "status": "present",
                "size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )

    add_file("finance_archive_config", config.multi_state.finance_archive_config_path)
    add_file("student_training_config", config.training.training_config_path)
    if config.training.ccgr_task_distribution_path is not None:
        add_file("ccgr_task_distribution", config.training.ccgr_task_distribution_path)
    if config.contribution_validation.observation_path is not None:
        add_file(
            "contribution_validation_observations",
            config.contribution_validation.observation_path,
        )
    for snapshot in config.training.external_benchmarks:
        add_file(f"external_benchmark:{snapshot.benchmark_id}", snapshot.path)
    for index, path in enumerate(config.refinement_dynamics.real_round_artifact_paths):
        add_file(f"real_vtdo_round:{index}", path)
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
