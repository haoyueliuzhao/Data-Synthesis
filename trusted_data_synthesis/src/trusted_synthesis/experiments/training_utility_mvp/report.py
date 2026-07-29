from __future__ import annotations

import json
from pathlib import Path

from trusted_synthesis.core.evaluation.utility import UtilityCohort
from trusted_synthesis.hashing import canonical_hash

from .schema import (
    CohortEvaluationResult,
    CohortTrainingResult,
    TrainingUtilityDataManifest,
    TrainingUtilityMVPConfig,
    TrainingUtilityMVPReport,
)

_DELTA_METRICS = (
    "response_contract_rate",
    "evidence_recall",
    "evidence_precision",
    "execution_coverage",
    "operation_grounding_score",
    "tool_necessity_score",
    "operation_exact_rate",
    "answer_exact_rate",
    "citation_exact_rate",
    "multi_hop_exact_rate",
    "distractor_robustness_rate",
    "end_to_end_rate",
)


def build_training_utility_report(
    config: TrainingUtilityMVPConfig,
    data_manifest: TrainingUtilityDataManifest,
    base_evaluation: CohortEvaluationResult,
    training_results: tuple[CohortTrainingResult, ...],
    cohort_evaluations: tuple[CohortEvaluationResult, ...],
) -> TrainingUtilityMVPReport:
    expected = set(UtilityCohort)
    if {item.cohort for item in training_results} != expected:
        raise ValueError("training report requires D1 through D5")
    if {item.cohort for item in cohort_evaluations} != {item.value for item in expected}:
        raise ValueError("evaluation report requires D1 through D5")
    if any(item.config_hash != config.config_hash for item in training_results):
        raise ValueError("cohort training config hashes do not match")
    evaluation_hashes = {
        base_evaluation.evaluation_dataset_hash,
        *(item.evaluation_dataset_hash for item in cohort_evaluations),
    }
    if evaluation_hashes != {data_manifest.evaluation_dataset_hash}:
        raise ValueError("all models must use the same frozen evaluation set")
    cohort_manifest_hashes = {item.cohort: item.dataset_hash for item in data_manifest.cohorts}
    if any(cohort_manifest_hashes[item.cohort] != item.dataset_hash for item in training_results):
        raise ValueError("training result does not match the frozen cohort dataset")
    deltas = {
        item.cohort: {
            metric: _delta(item, base_evaluation, metric)
            for metric in _DELTA_METRICS
            if getattr(item, metric) is not None and getattr(base_evaluation, metric) is not None
        }
        for item in cohort_evaluations
    }
    ranking = tuple(
        item.cohort
        for item in sorted(
            cohort_evaluations,
            key=lambda item: (
                -item.end_to_end_rate,
                -item.operation_exact_rate,
                -item.evidence_recall,
                item.cohort,
            ),
        )
    )
    best = next(item for item in cohort_evaluations if item.cohort == ranking[0])
    limitations = (
        "MVP uses one seed, "
        f"{config.cohort_size} training records per cohort, and "
        f"{data_manifest.evaluation_record_count} held-out tasks.",
        "The contract suite covers three domains but only one task family per domain.",
        "Evaluation is evidence-given and plan-given; no live retrieval tool is exercised.",
        "DeepSeek Quality Critic labels are advisory rather than human annotations.",
        "Results establish pipeline feasibility, not statistically powered utility claims.",
    )
    identity = {
        "config_hash": config.config_hash,
        "data_manifest_id": data_manifest.manifest_id,
        "base_result_hash": base_evaluation.result_hash,
        "training_result_hashes": tuple(item.result_hash for item in training_results),
        "evaluation_result_hashes": tuple(item.result_hash for item in cohort_evaluations),
    }
    return TrainingUtilityMVPReport(
        report_id=canonical_hash(identity, prefix="training_utility_mvp_report:"),
        config_hash=config.config_hash,
        data_manifest_id=data_manifest.manifest_id,
        base_evaluation=base_evaluation,
        cohort_training=tuple(sorted(training_results, key=lambda item: item.cohort)),
        cohort_evaluations=tuple(sorted(cohort_evaluations, key=lambda item: item.cohort)),
        best_cohort_by_end_to_end=best.cohort,
        best_end_to_end_rate=best.end_to_end_rate,
        cohort_deltas_vs_base=deltas,
        cohort_ranking=ranking,
        completed_cohort_count=len(cohort_evaluations),
        status="completed",
        limitations=limitations,
    )


def write_training_utility_report(
    output_dir: Path,
    report: TrainingUtilityMVPReport,
    data_manifest: TrainingUtilityDataManifest,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "training_utility_mvp_report.json").write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "training_utility_mvp_report.md").write_text(
        _render_markdown(report, data_manifest),
        encoding="utf-8",
    )


def load_training_result(path: Path) -> CohortTrainingResult:
    return CohortTrainingResult.model_validate_json(path.read_text(encoding="utf-8"))


def load_evaluation_result(path: Path) -> CohortEvaluationResult:
    return CohortEvaluationResult.model_validate_json(path.read_text(encoding="utf-8"))


def _delta(
    result: CohortEvaluationResult,
    base: CohortEvaluationResult,
    metric: str,
) -> float:
    return float(getattr(result, metric)) - float(getattr(base, metric))


def _render_markdown(
    report: TrainingUtilityMVPReport,
    manifest: TrainingUtilityDataManifest,
) -> str:
    evaluations = (report.base_evaluation, *report.cohort_evaluations)
    lines = [
        "# v0.8 Training Utility MVP Report",
        "",
        "## Experiment Contract",
        "",
        f"- Report ID: {report.report_id}",
        f"- Agent source: {manifest.source_agent_model} / {manifest.source_agent_run_id}",
        f"- Critic models: {', '.join(manifest.critic_model_ids)}",
        f"- Training records: {manifest.cohorts[0].record_count} per cohort",
        f"- Held-out records: {manifest.evaluation_record_count}",
        (
            f"- Model and method: {report.cohort_training[0].base_model}, "
            "BF16 LoRA SFT, identical settings for D1-D5"
        ),
        "- Evaluation track: evidence-given + plan-given; strict structured replay matching",
        "",
        "## Main Results",
        "",
        "| Dataset | Contract | Evidence R | Exec Cov | Grounding | Tool | Operation | "
        "Answer | Citation | Multi-hop | Distractor | End-to-end |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for evaluation in evaluations:
        lines.append(
            "| "
            + " | ".join(
                (
                    evaluation.cohort,
                    _pct(evaluation.response_contract_rate),
                    _pct(evaluation.evidence_recall),
                    _pct(evaluation.execution_coverage),
                    _pct(evaluation.operation_grounding_score),
                    _pct(evaluation.tool_necessity_score),
                    _pct(evaluation.operation_exact_rate),
                    _pct(evaluation.answer_exact_rate),
                    _pct(evaluation.citation_exact_rate),
                    _pct(evaluation.multi_hop_exact_rate),
                    _pct(evaluation.distractor_robustness_rate),
                    _pct(evaluation.end_to_end_rate),
                )
            )
            + " |"
        )
    lines.extend(
        (
            "",
            "## Training Audit",
            "",
            "| Dataset | Steps | Loss | Runtime (min) | Peak GPU (GiB) |",
            "| --- | ---: | ---: | ---: | ---: |",
        )
    )
    for training in report.cohort_training:
        loss = "n/a" if training.final_train_loss is None else f"{training.final_train_loss:.4f}"
        lines.append(
            f"| {training.cohort} | {training.completed_steps} | "
            f"{loss} | {training.train_runtime_seconds / 60:.2f} | "
            f"{training.peak_gpu_memory_bytes / 2**30:.2f} |"
        )
    lines.extend(
        (
            "",
            "## Interpretation Boundary",
            "",
            *[f"- {item}" for item in report.limitations],
            "",
            "The MVP passes only if all five cohorts use the same model snapshot, "
            "hyperparameters, cohort size, domain balance, and hidden evaluation set. "
            "Deltas therefore isolate the data construction policy within this "
            "small contract suite.",
            "",
        )
    )
    return "\n".join(lines)


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"
