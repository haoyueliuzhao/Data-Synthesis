from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

from trusted_synthesis.core.evaluation.counterfactual import (
    CounterfactualPlanner,
    CounterfactualSliceMetrics,
    TypedCounterfactualGenerator,
)
from trusted_synthesis.core.evaluation.schema import ReleaseDecision
from trusted_synthesis.core.feedback import (
    FeedbackExposure,
    FeedbackRoute,
    FeedbackSignal,
    contract_feedback,
)
from trusted_synthesis.core.refinement import (
    SynthesisCell,
    build_synthesis_cell,
    clause_calibration_from_metrics,
)
from trusted_synthesis.experiments.counterfactual_finance_fixture import (
    build_finance_counterfactual_cases,
)
from trusted_synthesis.experiments.counterfactual_validation import (
    compile_counterfactual_context,
)
from trusted_synthesis.experiments.cross_domain_contract_suite.fixtures import (
    build_pattern_validation_cases,
)
from trusted_synthesis.hashing import canonical_hash

from .builder import compile_v09_refinement
from .schema import (
    V09InitialBuildReport,
    V09RefinementConfig,
    V09RefinementManifest,
)


def build_v09_offline_pilot(
    config: V09RefinementConfig,
    *,
    tasks_per_domain: int = 3,
) -> tuple[
    V09InitialBuildReport,
    V09RefinementManifest,
    tuple[FeedbackExposure, ...],
    tuple[FeedbackSignal, ...],
]:
    """Exercise feedback allocation without claiming real-agent Round-0 evidence."""

    if tasks_per_domain < 1:
        raise ValueError("v0.9 offline pilot requires at least one task per domain")
    cases = (
        *build_finance_counterfactual_cases(count=tasks_per_domain),
        *build_pattern_validation_cases(per_domain=tasks_per_domain),
    )
    exposures: list[FeedbackExposure] = []
    signals_by_id: dict[str, FeedbackSignal] = {}
    task_cells: dict[str, SynthesisCell] = {}
    task_domains: dict[str, str] = {}
    calibration_rows: dict[str, list[dict[str, float | bool]]] = defaultdict(list)
    domain_tasks = Counter[str]()
    domain_valid_cases = Counter[str]()
    clean_accepted_count = 0
    opportunity_count = 0
    generated_case_count = 0
    detected_case_count = 0
    valid_case_count = 0
    expected_root_match_count = 0

    for case in cases:
        domain_tasks[case.domain] += 1
        context, runtime = compile_counterfactual_context(case)
        cell = build_synthesis_cell(
            case.task.public,
            case.corpus,
            case.task.oracle.gold_evidence_ids,
        )
        task_cells[case.task.task_id] = cell
        task_domains[case.task.task_id] = case.domain
        pattern_id = cell.pattern_id
        clean_assessment = runtime.evaluate(
            context.contract,
            context.task,
            context.corpus,
            context.proof_graph,
            context.source_trajectory,
        )
        clean_accepted_count += int(clean_assessment.decision == ReleaseDecision.ACCEPTED)
        task_exposures, _ = contract_feedback(
            domain=case.domain,
            pattern_id=pattern_id,
            contract=context.contract,
            assessment=clean_assessment,
        )
        exposures.extend(task_exposures)

        planner = CounterfactualPlanner(case.counterfactual_registry)
        generator = TypedCounterfactualGenerator(
            case.counterfactual_registry,
            minimality_threshold=config.offline_minimality_threshold,
        )
        opportunities = planner.plan(context)
        opportunity_count += len(opportunities)
        for counterfactual in generator.generate(context, opportunities):
            generated_case_count += 1
            assessment = runtime.evaluate(
                context.contract,
                context.task,
                context.corpus,
                context.proof_graph,
                counterfactual.trajectory,
            )
            detected = assessment.decision == ReleaseDecision.REJECTED
            root_matched = counterfactual.expected_root_clause in set(
                assessment.root_failure_clause_ids
            )
            root_f1 = _set_f1(
                (counterfactual.expected_root_clause,),
                assessment.root_failure_clause_ids,
            )
            closure_f1 = _set_f1(
                counterfactual.expected_failed_clauses,
                assessment.failed_clause_ids,
            )
            detected_case_count += int(detected)
            expected_root_match_count += int(root_matched)
            valid = counterfactual.minimality.passed and detected and root_matched
            clause_by_id = {clause.clause_id: clause for clause in context.contract.clauses}
            expected_root_kind = clause_by_id[counterfactual.expected_root_clause].clause_kind
            calibration_rows[expected_root_kind].append(
                {
                    "valid": valid,
                    "detected": detected,
                    "minimal": counterfactual.minimality.passed,
                    "minimality_score": counterfactual.minimality_score,
                    "root_f1": root_f1,
                    "closure_f1": closure_f1,
                }
            )
            if not valid:
                continue
            valid_case_count += 1
            domain_valid_cases[case.domain] += 1
            _, case_signals = contract_feedback(
                domain=case.domain,
                pattern_id=pattern_id,
                contract=context.contract,
                assessment=assessment,
            )
            for signal in case_signals:
                signals_by_id[signal.signal_id] = signal

    unique_exposures = _unique_exposures(exposures)
    signals = tuple(signals_by_id[key] for key in sorted(signals_by_id))
    clause_metrics = {
        clause_kind: _slice_metrics(rows) for clause_kind, rows in sorted(calibration_rows.items())
    }
    clause_calibration, calibration_hash = clause_calibration_from_metrics(clause_metrics)
    target_probabilities = _target_cell_distribution(
        task_cells,
        task_domains,
        config.domain_weights,
    )
    manifest = compile_v09_refinement(
        config,
        exposures=unique_exposures,
        signals=signals,
        feedback_source="typed_counterfactual_offline_mvp",
        round0_real_agent_feedback=False,
        task_cells=task_cells,
        clause_calibration=clause_calibration,
        calibration_manifest_hash=calibration_hash,
        target_probabilities=target_probabilities,
    )
    full_ccgr = next(item for item in manifest.ccgr_updates if item.ablation_id == "full_ccgr")
    clean_rate = _rate(clean_accepted_count, len(cases))
    detection_rate = _rate(detected_case_count, generated_case_count)
    valid_rate = _rate(valid_case_count, generated_case_count)
    root_match_rate = _rate(expected_root_match_count, generated_case_count)
    checks = {
        "clean_contract_acceptance_not_complete": clean_rate != 1.0,
        "no_counterfactual_cases_generated": generated_case_count == 0,
        "offline_valid_case_rate_below_contract": (
            valid_rate < config.offline_minimum_valid_case_rate
        ),
        "offline_root_match_rate_below_contract": (
            root_match_rate < config.offline_minimum_root_match_rate
        ),
        "domain_coverage_incomplete": set(domain_tasks) != {"finance", "legal", "science"},
        "no_agent_capability_feedback": not any(
            item.route == FeedbackRoute.AGENT_CAPABILITY_GAP for item in signals
        ),
        "lambda_ablation_incomplete": {item.lambda_value for item in manifest.allocations}
        != {0.0, 0.5, 1.0},
        "ccgr_ablation_incomplete": len(manifest.ccgr_updates) != 6,
        "full_ccgr_update_blocked": full_ccgr.status != "passed",
        "clause_calibration_coverage_below_contract": (
            manifest.calibration_coverage_rate < config.offline_minimum_calibration_coverage
        ),
    }
    failures = tuple(key for key, failed in checks.items() if failed)
    limitations = (
        "This run uses typed counterfactual trajectories, not real model failures.",
        (
            "It validates routing, aggregation, and allocation; it does not establish "
            "training utility."
        ),
        "The 30-task online Host-Instrumented gate remains mandatory before GPU training.",
        "External native benchmarks and multi-seed training have not been executed.",
        "Selected=used=cited evidence remains a controlled-task assumption.",
        "This offline slice contains no synthesis-defect root, so beta=0 matches Full CCGR.",
        "Observed root Clause kinds without targeted calibration retain zero feedback weight.",
    )
    identity = {
        "config_hash": config.config_hash,
        "manifest_id": manifest.manifest_id,
        "tasks_per_domain": tasks_per_domain,
        "source_task_ids": tuple(sorted(case.task.task_id for case in cases)),
        "signal_ids": tuple(item.signal_id for item in signals),
        "failures": failures,
    }
    report = V09InitialBuildReport(
        report_id=canonical_hash(identity, prefix="training_utility_v09_initial_report:"),
        config_hash=config.config_hash,
        manifest_id=manifest.manifest_id,
        tasks_per_domain=tasks_per_domain,
        source_task_count=len(cases),
        clean_accepted_count=clean_accepted_count,
        opportunity_count=opportunity_count,
        generated_case_count=generated_case_count,
        detected_case_count=detected_case_count,
        valid_case_count=valid_case_count,
        expected_root_match_count=expected_root_match_count,
        domain_task_counts=dict(sorted(domain_tasks.items())),
        domain_valid_case_counts=dict(sorted(domain_valid_cases.items())),
        feedback_route_counts=manifest.feedback_route_counts,
        clean_acceptance_rate=clean_rate,
        detection_rate=detection_rate,
        valid_case_rate=valid_rate,
        expected_root_match_rate=root_match_rate,
        synthesis_cell_count=len(manifest.synthesis_cells),
        calibrated_clause_kind_count=len(manifest.clause_calibration),
        calibration_coverage_rate=manifest.calibration_coverage_rate,
        ccgr_ablation_count=len(manifest.ccgr_updates),
        full_ccgr_kl_divergence=full_ccgr.kl_divergence,
        full_ccgr_total_variation_distance=full_ccgr.total_variation_distance,
        status="passed" if not failures else "failed",
        failures=failures,
        limitations=limitations,
    )
    return report, manifest, unique_exposures, signals


def write_v09_initial_artifacts(
    output_dir: Path,
    report: V09InitialBuildReport,
    manifest: V09RefinementManifest,
    exposures: tuple[FeedbackExposure, ...],
    signals: tuple[FeedbackSignal, ...],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "v09_initial_build_report.json", report)
    _write_json(output_dir / "v09_refinement_manifest.json", manifest)
    _write_jsonl(output_dir / "feedback_exposures.jsonl", exposures)
    _write_jsonl(output_dir / "feedback_signals.jsonl", signals)
    _write_jsonl(output_dir / "synthesis_cells.jsonl", manifest.synthesis_cells)
    _write_jsonl(output_dir / "clause_feedback.jsonl", manifest.clause_feedback)
    _write_json(output_dir / "ccgr_policy_updates.json", manifest.ccgr_updates)
    (output_dir / "v09_initial_build_report.md").write_text(
        _render_markdown(report, manifest),
        encoding="utf-8",
    )


def _unique_exposures(
    values: list[FeedbackExposure],
) -> tuple[FeedbackExposure, ...]:
    by_key = {
        (item.task_id, item.domain, item.pattern_id, item.failure_family): item for item in values
    }
    return tuple(by_key[key] for key in sorted(by_key))


def _write_json(path: Path, value: object) -> None:
    payload = _json_value(value)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, values: tuple[object, ...]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for value in values:
            payload = _json_value(value)
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _json_value(value: object) -> object:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return value


def _render_markdown(
    report: V09InitialBuildReport,
    manifest: V09RefinementManifest,
) -> str:
    lines = [
        "# v0.9 Clause-Guided Refinement Initial Build",
        "",
        "## Status",
        "",
        f"- Offline contract pipeline: **{report.status}**",
        f"- Manifest status: **{manifest.status}**",
        "- Real-agent Round-0 feedback: **not executed**",
        "- External native benchmark: **not executed**",
        f"- Source tasks: {report.source_task_count}",
        f"- Typed counterfactual cases: {report.generated_case_count}",
        f"- Valid feedback cases: {report.valid_case_count}",
        "",
        "## Contract Metrics",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Clean acceptance | {report.clean_acceptance_rate:.2%} |",
        f"| Counterfactual detection | {report.detection_rate:.2%} |",
        f"| Valid case rate | {report.valid_case_rate:.2%} |",
        f"| Expected root match | {report.expected_root_match_rate:.2%} |",
        f"| Clause calibration coverage | {report.calibration_coverage_rate:.2%} |",
        f"| Synthesis cells | {report.synthesis_cell_count} |",
        f"| CCGR policy TV shift | {report.full_ccgr_total_variation_distance:.6f} |",
        f"| CCGR policy KL | {report.full_ccgr_kl_divergence:.6f} |",
        "",
        "## Domain Coverage",
        "",
        "| Domain | Source tasks | Valid cases |",
        "| --- | ---: | ---: |",
    ]
    for domain, count in sorted(report.domain_task_counts.items()):
        lines.append(f"| {domain} | {count} | {report.domain_valid_case_counts.get(domain, 0)} |")
    lines.extend(
        (
            "",
            "## Feedback Routing",
            "",
            "| Route | Signals |",
            "| --- | ---: |",
        )
    )
    for route, count in sorted(report.feedback_route_counts.items()):
        lines.append(f"| {route} | {count} |")
    lines.extend(
        (
            "",
            "## Causal Cohort Contract",
            "",
            (
                "| Cohort | Evidence | Proof graph | Executable program | "
                "Quality contract | Feedback |"
            ),
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        )
    )
    for cohort in manifest.cohort_contracts:
        lines.append(
            f"| {cohort.cohort.value} | {cohort.evidence_grounded} | "
            f"{cohort.proof_graph_required} | {cohort.executable_program_contract} | "
            f"{cohort.quality_contract_required} | {cohort.feedback_refined} |"
        )
    lines.extend(("", "## Interpretation Boundary", ""))
    lines.extend(f"- {item}" for item in report.limitations)
    if report.failures:
        lines.extend(("", "## Failed Checks", ""))
        lines.extend(f"- {item}" for item in report.failures)
    lines.append("")
    return "\n".join(lines)


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _set_f1(expected: tuple[str, ...], observed: tuple[str, ...]) -> float:
    expected_set = set(expected)
    observed_set = set(observed)
    true_positive = len(expected_set & observed_set)
    precision = _rate(true_positive, len(observed_set))
    recall = _rate(true_positive, len(expected_set))
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)


def _slice_metrics(
    rows: list[dict[str, float | bool]],
) -> CounterfactualSliceMetrics:
    generated = len(rows)
    valid = sum(bool(row["valid"]) for row in rows)
    detected = sum(bool(row["detected"]) for row in rows)
    return CounterfactualSliceMetrics(
        generated_case_count=generated,
        valid_case_count=valid,
        detected_case_count=detected,
        mutation_validity_rate=_rate(valid, generated),
        detection_rate=_rate(detected, generated),
        minimality_pass_rate=_rate(
            sum(bool(row["minimal"]) for row in rows),
            generated,
        ),
        mean_minimality_score=mean(float(row["minimality_score"]) for row in rows),
        root_cause_f1=mean(float(row["root_f1"]) for row in rows),
        failure_closure_f1=mean(float(row["closure_f1"]) for row in rows),
    )


def _target_cell_distribution(
    task_cells: dict[str, SynthesisCell],
    task_domains: dict[str, str],
    domain_weights: dict[str, float],
) -> dict[str, float]:
    by_domain = Counter(
        (task_domains[task_id], cell.cell_id) for task_id, cell in task_cells.items()
    )
    domain_totals = Counter(task_domains.values())
    targets: dict[str, float] = defaultdict(float)
    for (domain, cell_id), count in by_domain.items():
        targets[cell_id] += domain_weights[domain] * count / domain_totals[domain]
    return dict(sorted(targets.items()))
