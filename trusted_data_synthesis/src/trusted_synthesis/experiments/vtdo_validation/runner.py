from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from pathlib import Path

from trusted_synthesis.hashing import canonical_hash

from .dynamics import run_refinement_dynamics_experiment
from .real_states import run_real_state_space_experiment
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
    VTDOStudentTrainingConfig,
    VTDOValidationConfig,
    VTDOValidationManifest,
)
from .synthetic import run_synthetic_experiment
from .training import build_training_experiment_preflight, write_training_arms


def run_vtdo_validation_experiment(
    config: VTDOValidationConfig,
) -> VTDOValidationManifest:
    output_dir = config.output_dir
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"VTDO experiment output directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_paths: dict[str, str] = {}
    completed: list[str] = []
    blocked: list[str] = []
    limitations: list[str] = []
    experiment_config_path = output_dir / "experiment_config.json"
    _write_json(experiment_config_path, config.model_dump(mode="json"))
    artifact_paths["experiment_config"] = experiment_config_path.name
    input_manifest = _build_input_manifest(config)
    input_manifest_path = output_dir / "input_manifest.json"
    _write_json(input_manifest_path, input_manifest)
    artifact_paths["input_manifest"] = input_manifest_path.name

    synthetic, state_catalogs, phase_rows = run_synthetic_experiment(
        config.synthetic,
        experiment_id=config.experiment_id,
    )
    synthetic_path = output_dir / "synthetic_experiment_report.json"
    _write_json(synthetic_path, synthetic.model_dump(mode="json"))
    artifact_paths["synthetic_report"] = synthetic_path.name
    states_path = output_dir / "synthetic_states.jsonl"
    with states_path.open("w", encoding="utf-8") as output:
        for seed, states in sorted(state_catalogs.items()):
            for state in states:
                output.write(
                    json.dumps(
                        {"seed": seed, **state.model_dump(mode="json")},
                        sort_keys=True,
                    )
                    + "\n"
                )
    artifact_paths["synthetic_states"] = states_path.name
    metrics_path = output_dir / "synthetic_metric_points.csv"
    _write_metric_points(metrics_path, synthetic.metric_points)
    artifact_paths["synthetic_metrics"] = metrics_path.name
    phase_path = output_dir / "synthetic_phase_observations.csv"
    _write_rows(phase_path, phase_rows)
    artifact_paths["synthetic_phase"] = phase_path.name
    table_path = output_dir / "table1_synthetic_method_comparison.csv"
    write_synthetic_table(synthetic, table_path)
    artifact_paths["table1"] = table_path.name
    distribution_figure = output_dir / "figure2_distribution_evolution.svg"
    write_distribution_figure(synthetic, distribution_figure)
    artifact_paths["figure2"] = distribution_figure.name
    phase_figure = output_dir / "figure3_contribution_novelty_phase.svg"
    write_phase_figure(phase_rows, phase_figure)
    artifact_paths["figure3"] = phase_figure.name
    completed.append("synthetic_vtdo_baselines_and_ablations")

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
    artifact_paths["refinement_dynamics_report"] = refinement_path.name
    controlled_rounds_path = output_dir / "controlled_refinement_rounds.csv"
    _write_rows(controlled_rounds_path, refinement_execution.controlled_rows)
    artifact_paths["controlled_refinement_rounds"] = controlled_rounds_path.name
    fixed_rounds_path = output_dir / "fixed_potential_contraction_rounds.csv"
    _write_rows(fixed_rounds_path, refinement_execution.fixed_potential_rows)
    artifact_paths["fixed_potential_contraction_rounds"] = fixed_rounds_path.name
    real_rounds_path = output_dir / "real_refinement_rounds.csv"
    _write_rows(real_rounds_path, refinement_execution.real_rows)
    artifact_paths["real_refinement_rounds"] = real_rounds_path.name
    dynamics_table = output_dir / "table2_refinement_round_dynamics.csv"
    write_refinement_round_table(refinement, dynamics_table)
    artifact_paths["table2"] = dynamics_table.name
    checkpoint_table = output_dir / "table3_one_shot_vs_iterative.csv"
    write_refinement_checkpoint_table(refinement, checkpoint_table)
    artifact_paths["table3"] = checkpoint_table.name
    dynamics_figure = output_dir / "figure4_refinement_dynamics.svg"
    write_refinement_dynamics_figure(refinement, dynamics_figure)
    artifact_paths["figure4"] = dynamics_figure.name
    completed.extend(
        (
            "fixed_potential_contraction_control",
            "moving_potential_finite_step_dynamics",
        )
    )
    if not refinement.fixed_potential_contraction.projective_contraction_verified:
        blocked.append("fixed_potential_contraction_control")
        limitations.append(
            "The fixed-potential control did not meet its frozen contraction tolerance."
        )
    if refinement.real_refinement.status != "passed":
        blocked.append("financial_refinement_round_dynamics")
        limitations.append(
            "No complete, sequentially linked five-transition financial VTDO round "
            "sequence is available; real practical convergence and downstream round "
            "selection remain unevaluated."
        )

    real_report = None
    real_rows: tuple[dict[str, object], ...] = ()
    if config.real_state.enabled:
        real_report, real_rows = run_real_state_space_experiment(config.real_state)
        real_path = output_dir / "real_quotient_state_report.json"
        _write_json(real_path, real_report.model_dump(mode="json"))
        artifact_paths["real_state_report"] = real_path.name
        row_path = output_dir / "real_quotient_assignments.jsonl"
        with row_path.open("w", encoding="utf-8") as output:
            for row in real_rows:
                output.write(json.dumps(row, sort_keys=True) + "\n")
        artifact_paths["real_state_assignments"] = row_path.name
        completed.append("real_quotient_controlled_equivalence_probe")
        if real_report.status != "passed":
            blocked.append("current_code_full_replay_of_archived_omega")
            limitations.append(
                "The archived Agent run did not persist a source-complete Omega artifact; "
                "its frozen Quality Contract now drifts from reconstructed Pattern/Difficulty "
                "metadata, so the quotient result is a controlled partial replay."
            )

    training_preflight = None
    if config.training.enabled:
        student_config = VTDOStudentTrainingConfig.from_json(config.training.training_config_path)
        student_config_path = output_dir / "student_training_config.json"
        _write_json(student_config_path, student_config.model_dump(mode="json"))
        artifact_paths["student_training_config"] = student_config_path.name
        training_preflight, arms = build_training_experiment_preflight(
            config.training,
            agent_artifact_dir=config.real_state.agent_artifact_dir,
            real_state_rows=real_rows,
        )
        preflight_path = output_dir / "training_preflight.json"
        _write_json(preflight_path, training_preflight.model_dump(mode="json"))
        artifact_paths["training_preflight"] = preflight_path.name
        artifact_paths.update(
            {
                f"training_{key}": str(Path("training_arms") / Path(value).name)
                for key, value in write_training_arms(
                    output_dir / "training_arms",
                    arms,
                ).items()
            }
        )
        completed.append("b1_b5_training_capacity_preflight")
        if not training_preflight.formal_training_ready:
            blocked.append("b1_b5_fixed_token_training")
            limitations.extend(training_preflight.blockers)
        if training_preflight.external_benchmark_status != "ready":
            blocked.append("external_finance_benchmark_evaluation")

    limitations.extend(
        (
            "Synthetic exact contribution is a controlled estimator check, not an empirical "
            "causal contribution estimate.",
            "Strict convergence is claimed only for the frozen-potential control; the "
            "production moving-potential loop is reported with finite-step practical "
            "stability diagnostics.",
            "Surface variants test quotient invariance but do not create additional real states.",
        )
    )
    limitations_tuple = tuple(sorted(set(limitations)))
    report_path = output_dir / "vtdo_validation_report.md"
    write_markdown_report(
        report_path,
        synthetic=synthetic,
        refinement=refinement,
        real=real_report,
        training=training_preflight,
        limitations=limitations_tuple,
    )
    artifact_paths["markdown_report"] = report_path.name

    repo_root = Path(__file__).resolve().parents[4]
    git_commit = _git(repo_root, ("rev-parse", "HEAD"), fallback="unknown")
    git_worktree_dirty = bool(_git(repo_root, ("status", "--porcelain"), fallback="unknown"))
    if blocked:
        status = "partial" if completed else "blocked"
    else:
        status = "passed"
    values = {
        "experiment_id": config.experiment_id,
        "config_hash": config.config_hash,
        "synthetic_report_hash": synthetic.artifact_hash,
        "refinement_dynamics_report_hash": refinement.report_hash,
        "real_state_report_hash": real_report.report_hash if real_report else None,
        "training_preflight_hash": (training_preflight.report_hash if training_preflight else None),
        "input_manifest_hash": input_manifest["manifest_hash"],
        "completed_components": tuple(completed),
        "blocked_components": tuple(sorted(set(blocked))),
        "artifact_paths": dict(sorted(artifact_paths.items())),
        "git_commit": git_commit,
        "git_worktree_dirty": git_worktree_dirty,
        "status": status,
        "limitations": limitations_tuple,
    }
    manifest = VTDOValidationManifest(
        **values,
        manifest_hash=canonical_hash(values, prefix="vtdo_validation_manifest:"),
    )
    manifest_path = output_dir / "manifest.json"
    _write_json(manifest_path, manifest.model_dump(mode="json"))
    return manifest


def _write_metric_points(path: Path, values) -> None:
    rows = [item.model_dump(mode="json") for item in values]
    _write_rows(path, rows)


def _write_rows(path: Path, rows) -> None:
    values = tuple(rows)
    if not values:
        path.write_text("", encoding="utf-8")
        return
    fields = tuple(values[0])
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(values)


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _build_input_manifest(config: VTDOValidationConfig) -> dict[str, object]:
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

    add_file("agent_config", config.real_state.agent_config_path)
    if config.real_state.agent_artifact_dir.is_dir():
        for path in sorted(config.real_state.agent_artifact_dir.iterdir()):
            if path.is_file():
                add_file(f"agent_artifact:{path.name}", path)
    else:
        entries.append(
            {
                "role": "agent_artifact_directory",
                "path": str(config.real_state.agent_artifact_dir),
                "status": "missing",
            }
        )
    add_file("student_training_config", config.training.training_config_path)
    if config.training.ccgr_manifest_path is not None:
        add_file("ccgr_manifest", config.training.ccgr_manifest_path)
    if config.training.vtdo_materialization_path is not None:
        add_file("vtdo_materialization", config.training.vtdo_materialization_path)
    for index, path in enumerate(config.training.external_benchmark_paths):
        add_file(f"external_benchmark:{index}", path)
    for index, path in enumerate(config.refinement_dynamics.real_round_artifact_paths):
        if path.is_dir():
            for artifact_path in sorted(path.glob("*.json*")):
                add_file(f"real_vtdo_round:{index}:{artifact_path.name}", artifact_path)
        else:
            add_file(f"real_vtdo_round:{index}", path)
    values: dict[str, object] = {
        "experiment_config_hash": config.config_hash,
        "source_tree_hash": _source_tree_hash(repo_root),
        "entries": entries,
    }
    return {
        **values,
        "manifest_hash": canonical_hash(values, prefix="vtdo_input_manifest:"),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_tree_hash(repo_root: Path) -> str:
    roots = (repo_root / "src" / "trusted_synthesis", repo_root / "tests")
    files = [repo_root / "pyproject.toml"]
    for root in roots:
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
