from __future__ import annotations

import json
from pathlib import Path

from trusted_synthesis.experiments.training_utility_mvp.schema import (
    CohortEvaluationResult,
    CohortTrainingResult,
    TrainingUtilityMVPConfig,
)
from trusted_synthesis.hashing import canonical_hash

from .schema import (
    V09Cohort,
    V09TrainingDataManifest,
    V09TrainingUtilityReport,
)

_DELTA_METRICS = (
    "response_contract_rate",
    "action_plan_contract_rate",
    "answer_decision_contract_rate",
    "host_execution_success_rate",
    "execution_replay_valid_rate",
    "evidence_recall",
    "evidence_precision",
    "execution_coverage",
    "operation_grounding_score",
    "tool_necessity_score",
    "operation_exact_rate",
    "answer_exact_rate",
    "citation_exact_rate",
    "verification_exact_rate",
    "multi_hop_exact_rate",
    "distractor_robustness_rate",
    "end_to_end_rate",
)


def build_v09_training_utility_report(
    config: TrainingUtilityMVPConfig,
    data_manifest: V09TrainingDataManifest,
    base_evaluation: CohortEvaluationResult,
    training_results: tuple[CohortTrainingResult, ...],
    cohort_evaluations: tuple[CohortEvaluationResult, ...],
) -> V09TrainingUtilityReport:
    """Validate and summarize a completed frozen C1-C4 comparison."""

    expected = {item.value for item in V09Cohort}
    if {item.cohort for item in training_results} != expected:
        raise ValueError("v0.9 training report requires exactly C1 through C4")
    if {item.cohort for item in cohort_evaluations} != expected:
        raise ValueError("v0.9 evaluation report requires exactly C1 through C4")
    if any(item.status != "completed" for item in training_results):
        raise ValueError("v0.9 report cannot include incomplete training results")
    if any(item.status != "completed" for item in cohort_evaluations):
        raise ValueError("v0.9 report cannot include incomplete evaluations")
    if any(item.config_hash != config.config_hash for item in training_results):
        raise ValueError("v0.9 cohort training config hashes do not match")
    manifest_by_cohort = {item.cohort.value: item for item in data_manifest.cohorts}
    for result in training_results:
        if result.dataset_hash != manifest_by_cohort[result.cohort].dataset_hash:
            raise ValueError(f"{result.cohort} does not match its frozen dataset")
    evaluation_hashes = {
        base_evaluation.evaluation_dataset_hash,
        *(item.evaluation_dataset_hash for item in cohort_evaluations),
    }
    if evaluation_hashes != {data_manifest.evaluation_dataset_hash}:
        raise ValueError("all v0.9 models must use the same frozen evaluation set")

    by_cohort = {item.cohort: item for item in cohort_evaluations}
    deltas = {
        cohort: {
            metric: _delta(result, base_evaluation, metric)
            for metric in _DELTA_METRICS
            if getattr(result, metric) is not None
            and getattr(base_evaluation, metric) is not None
        }
        for cohort, result in sorted(by_cohort.items())
    }
    c3 = by_cohort[V09Cohort.VERIFIED_STATIC.value]
    c4 = by_cohort[V09Cohort.FEEDBACK_REFINED.value]
    c4_minus_c3 = {
        metric: _delta(c4, c3, metric)
        for metric in _DELTA_METRICS
        if getattr(c4, metric) is not None and getattr(c3, metric) is not None
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
    causal_claim_status = (
        "identified"
        if data_manifest.causal_status == "online_ready"
        and data_manifest.round0_real_agent_feedback
        else "not_identified"
    )
    limitations = [
        "The experiment uses one training seed and one frozen held-out contract suite.",
        "Evaluation is evidence-given and host-instrumented, not open retrieval.",
        "External benchmarks have not been executed.",
    ]
    if causal_claim_status == "not_identified":
        limitations.append(
            "C4 uses offline counterfactual calibration; C4-C3 differences do not "
            "identify the benefit of real-agent feedback refinement."
        )
    identity = {
        "config_hash": config.config_hash,
        "data_manifest_id": data_manifest.manifest_id,
        "base_result_hash": base_evaluation.result_hash,
        "training_result_hashes": tuple(
            sorted(item.result_hash for item in training_results)
        ),
        "evaluation_result_hashes": tuple(
            sorted(item.result_hash for item in cohort_evaluations)
        ),
        "causal_claim_status": causal_claim_status,
    }
    return V09TrainingUtilityReport(
        report_id=canonical_hash(identity, prefix="training_utility_v09_report:"),
        config_hash=config.config_hash,
        data_manifest_id=data_manifest.manifest_id,
        causal_status=data_manifest.causal_status,
        causal_claim_status=causal_claim_status,
        base_evaluation=base_evaluation,
        cohort_training=tuple(sorted(training_results, key=lambda item: item.cohort)),
        cohort_evaluations=tuple(
            sorted(cohort_evaluations, key=lambda item: item.cohort)
        ),
        cohort_deltas_vs_base=deltas,
        c4_minus_c3=c4_minus_c3,
        cohort_ranking=ranking,
        completed_cohort_count=len(cohort_evaluations),
        limitations=tuple(limitations),
        status="completed",
    )


def write_v09_training_utility_report(
    output_dir: Path,
    report: V09TrainingUtilityReport,
    data_manifest: V09TrainingDataManifest,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "training_utility_v09_report.json").write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "training_utility_v09_report.md").write_text(
        _render_markdown(report, data_manifest),
        encoding="utf-8",
    )


def _delta(
    result: CohortEvaluationResult,
    baseline: CohortEvaluationResult,
    metric: str,
) -> float:
    return float(getattr(result, metric)) - float(getattr(baseline, metric))


def _render_markdown(
    report: V09TrainingUtilityReport,
    manifest: V09TrainingDataManifest,
) -> str:
    evaluations = (report.base_evaluation, *report.cohort_evaluations)
    lines = [
        "# v0.9 Training Utility Report",
        "",
        "## Frozen Contract",
        "",
        f"- Report ID: `{report.report_id}`",
        f"- Data manifest: `{manifest.manifest_id}`",
        f"- Causal status: `{report.causal_status}`",
        f"- Causal claim status: `{report.causal_claim_status}`",
        f"- Records per cohort: {manifest.cohort_example_budget:,}",
        f"- Supervised tokens per cohort: {manifest.supervised_token_budget:,}",
        f"- Held-out records: {manifest.evaluation_record_count:,}",
        "",
        "## Main Results",
        "",
        "| Dataset | Plan contract | Host execution | Evidence R | Operation | "
        "Answer | Citation | End-to-end |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in evaluations:
        lines.append(
            f"| {item.cohort} | {_pct(item.action_plan_contract_rate)} | "
            f"{_pct(item.host_execution_success_rate)} | {_pct(item.evidence_recall)} | "
            f"{_pct(item.operation_exact_rate)} | {_pct(item.answer_exact_rate)} | "
            f"{_pct(item.citation_exact_rate)} | {_pct(item.end_to_end_rate)} |"
        )
    lines.extend(
        (
            "",
            "## C4 Minus C3",
            "",
            *[
                f"- `{metric}`: {value:+.4f}"
                for metric, value in sorted(report.c4_minus_c3.items())
            ],
            "",
            "## Training Audit",
            "",
            "| Cohort | Steps | Supervised tokens | Deviation | Loss | Runtime (min) | "
            "Peak GPU (GiB) |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        )
    )
    for item in report.cohort_training:
        loss = "n/a" if item.final_train_loss is None else f"{item.final_train_loss:.4f}"
        deviation = (
            "n/a"
            if item.token_budget_deviation_rate is None
            else f"{item.token_budget_deviation_rate * 100:.3f}%"
        )
        lines.append(
            f"| {item.cohort} | {item.completed_steps} | "
            f"{item.supervised_token_count or 0:,} | {deviation} | {loss} | "
            f"{item.train_runtime_seconds / 60:.2f} | "
            f"{item.peak_gpu_memory_bytes / 2**30:.2f} |"
        )
    lines.extend(
        (
            "",
            "## Interpretation Boundary",
            "",
            *[f"- {item}" for item in report.limitations],
            "",
        )
    )
    return "\n".join(lines)


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"
