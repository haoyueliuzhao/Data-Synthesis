from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from statistics import mean

from trusted_synthesis.core.evaluation.contracts.schema import (
    ContractQualityAssessment,
)
from trusted_synthesis.core.evaluation.counterfactual.context import CounterfactualContext
from trusted_synthesis.core.evaluation.counterfactual.generator import (
    COUNTERFACTUAL_GENERATOR_VERSION,
    TypedCounterfactualGenerator,
)
from trusted_synthesis.core.evaluation.counterfactual.planner import (
    CounterfactualPlanner,
)
from trusted_synthesis.core.evaluation.counterfactual.registry import (
    CounterfactualOperatorRegistry,
)
from trusted_synthesis.core.evaluation.counterfactual.schema import (
    CounterfactualCalibrationReport,
    CounterfactualCase,
    CounterfactualCaseEvaluation,
    CounterfactualSliceMetrics,
)
from trusted_synthesis.core.evaluation.schema import ReleaseDecision
from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.hashing import canonical_hash

COUNTERFACTUAL_CALIBRATION_VERSION = "counterfactual_calibration.v3"

AssessmentCallback = Callable[
    [CounterfactualContext, Trajectory],
    ContractQualityAssessment,
]


def calibrate_counterfactuals(
    contexts: Iterable[CounterfactualContext],
    registry: CounterfactualOperatorRegistry,
    evaluate: AssessmentCallback,
    *,
    minimality_threshold: float = 0.9,
) -> tuple[CounterfactualCalibrationReport, tuple[CounterfactualCase, ...]]:
    context_items = tuple(contexts)
    planner = CounterfactualPlanner(registry)
    generator = TypedCounterfactualGenerator(
        registry,
        minimality_threshold=minimality_threshold,
    )
    cases: list[CounterfactualCase] = []
    context_by_case: dict[str, CounterfactualContext] = {}
    mutable_clause_ids: set[str] = set()
    opportunity_count = 0
    clean_false_positives = 0
    generated_source_clauses: set[str] = set()
    for context in context_items:
        context.validate()
        clean = evaluate(context, context.source_trajectory)
        clean_false_positives += int(clean.decision != ReleaseDecision.ACCEPTED)
        mutable_clause_ids.update(
            clause.clause_id
            for clause in context.contract.clauses
            if clause.mutation_specs
        )
        opportunities = planner.plan(context)
        generated_source_clauses.update(
            opportunity.source_clause_id for opportunity in opportunities
        )
        opportunity_count += len(opportunities)
        for case in generator.generate(context, opportunities):
            cases.append(case)
            context_by_case[case.counterfactual_id] = context

    evaluations = []
    for case in cases:
        context = context_by_case[case.counterfactual_id]
        assessment = evaluate(context, case.trajectory)
        expected_roots = (case.expected_root_clause,)
        expected_closure = case.expected_failed_clauses
        observed_roots = assessment.root_failure_clause_ids
        observed_closure = assessment.failed_clause_ids
        root_metrics = _set_metrics(expected_roots, observed_roots)
        closure_metrics = _set_metrics(expected_closure, observed_closure)
        evaluations.append(
            CounterfactualCaseEvaluation(
                counterfactual_id=case.counterfactual_id,
                assessment_id=assessment.assessment_id,
                source_clause_id=case.source_clause_id,
                source_clause_kind=case.source_clause_kind,
                mutation_family=case.mutation_family,
                mutation_operator_id=case.mutation_operator_id,
                detected=assessment.decision == ReleaseDecision.REJECTED,
                expected_root_clause_ids=expected_roots,
                observed_root_clause_ids=observed_roots,
                expected_failed_clause_ids=expected_closure,
                observed_failed_clause_ids=observed_closure,
                root_precision=root_metrics[0],
                root_recall=root_metrics[1],
                root_f1=root_metrics[2],
                closure_precision=closure_metrics[0],
                closure_recall=closure_metrics[1],
                closure_f1=closure_metrics[2],
            )
        )

    detected_count = sum(item.detected for item in evaluations)
    minimal_cases = [item for item in cases if item.minimality.passed]
    valid_count = sum(
        item.detected and case.minimality.passed
        for item, case in zip(evaluations, cases, strict=True)
    )
    detection_precision, detection_recall, detection_f1 = _binary_metrics(
        detected_count,
        len(cases) - detected_count,
        clean_false_positives,
    )
    root_precision, root_recall, root_f1 = _macro_set_metrics(
        tuple(
            (item.expected_root_clause_ids, item.observed_root_clause_ids)
            for item in evaluations
        )
    )
    closure_precision, closure_recall, closure_f1 = _macro_set_metrics(
        tuple(
            (item.expected_failed_clause_ids, item.observed_failed_clause_ids)
            for item in evaluations
        )
    )
    uncovered_mutable_clause_ids = tuple(sorted(mutable_clause_ids - generated_source_clauses))
    exercised_operator_ids = {item.mutation_operator_id for item in cases}
    validity_rate = _rate(valid_count, len(cases))
    minimality_pass_rate = _rate(len(minimal_cases), len(cases))
    mean_minimality = mean(item.minimality_score for item in cases) if cases else 0.0
    thresholds = {
        "clean_false_positive_count_eq_0": clean_false_positives == 0,
        "mutation_validity_gt_0_95": validity_rate > 0.95,
        "minimality_score_gt_0_90": mean_minimality > 0.9,
        "minimality_pass_rate_gt_0_95": minimality_pass_rate > 0.95,
        "detection_f1_gt_0_95": detection_f1 > 0.95,
        "root_cause_f1_gt_0_90": root_f1 > 0.9,
        "failure_closure_f1_gt_0_85": closure_f1 > 0.85,
        "mutable_clause_coverage_gt_0_95": _rate(
            len(generated_source_clauses), len(mutable_clause_ids)
        )
        > 0.95,
        "operator_coverage_gt_0_95": _rate(
            len(exercised_operator_ids), len(registry.operator_ids)
        )
        > 0.95,
    }
    failures = tuple(key for key, passed in thresholds.items() if not passed)
    identity = {
        "version": COUNTERFACTUAL_CALIBRATION_VERSION,
        "operator_manifest_hash": registry.manifest_hash,
        "source_sample_ids": tuple(
            sorted(item.source_sample.sample_id for item in context_items)
        ),
        "counterfactual_ids": tuple(item.counterfactual_id for item in cases),
        "evaluation_ids": tuple(item.assessment_id for item in evaluations),
    }
    report = CounterfactualCalibrationReport(
        calibration_id=canonical_hash(identity, prefix="counterfactual_calibration:"),
        engine_version=(
            f"{COUNTERFACTUAL_GENERATOR_VERSION}+{COUNTERFACTUAL_CALIBRATION_VERSION}"
        ),
        operator_manifest_hash=registry.manifest_hash,
        source_sample_count=len(context_items),
        clean_false_positive_count=clean_false_positives,
        opportunity_count=opportunity_count,
        generated_case_count=len(cases),
        valid_case_count=valid_count,
        detected_case_count=detected_count,
        mutation_validity_rate=validity_rate,
        minimality_pass_rate=minimality_pass_rate,
        mean_minimality_score=mean_minimality,
        detection_precision=detection_precision,
        detection_recall=detection_recall,
        detection_f1=detection_f1,
        root_cause_precision=root_precision,
        root_cause_recall=root_recall,
        root_cause_f1=root_f1,
        failure_closure_precision=closure_precision,
        failure_closure_recall=closure_recall,
        failure_closure_f1=closure_f1,
        mutable_clause_count=len(mutable_clause_ids),
        covered_mutable_clause_count=len(generated_source_clauses),
        uncovered_mutable_clause_ids=uncovered_mutable_clause_ids,
        clause_coverage_rate=_rate(len(generated_source_clauses), len(mutable_clause_ids)),
        registered_operator_count=len(registry.operator_ids),
        exercised_operator_count=len(exercised_operator_ids),
        operator_coverage_rate=_rate(
            len(exercised_operator_ids),
            len(registry.operator_ids),
        ),
        mutation_family_counts=dict(
            sorted(Counter(item.mutation_family.value for item in cases).items())
        ),
        operator_counts=dict(
            sorted(Counter(item.mutation_operator_id for item in cases).items())
        ),
        mutation_family_metrics=_slice_reports(
            cases,
            evaluations,
            lambda case: case.mutation_family.value,
        ),
        operator_metrics=_slice_reports(
            cases,
            evaluations,
            lambda case: case.mutation_operator_id,
        ),
        source_clause_kind_metrics=_slice_reports(
            cases,
            evaluations,
            lambda case: case.source_clause_kind,
        ),
        case_evaluations=tuple(evaluations),
        status="passed" if not failures else "failed",
        failures=failures,
    )
    return report, tuple(cases)


def _set_metrics(
    expected: tuple[str, ...],
    observed: tuple[str, ...],
) -> tuple[float, float, float]:
    expected_set = set(expected)
    observed_set = set(observed)
    true_positive = len(expected_set & observed_set)
    precision = _rate(true_positive, len(observed_set))
    recall = _rate(true_positive, len(expected_set))
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return precision, recall, f1


def _macro_set_metrics(
    pairs: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...],
) -> tuple[float, float, float]:
    if not pairs:
        return 0.0, 0.0, 0.0
    values = tuple(_set_metrics(expected, observed) for expected, observed in pairs)
    return (
        mean(item[0] for item in values),
        mean(item[1] for item in values),
        mean(item[2] for item in values),
    )


def _binary_metrics(
    true_positive: int,
    false_negative: int,
    false_positive: int,
) -> tuple[float, float, float]:
    precision = _rate(true_positive, true_positive + false_positive)
    recall = _rate(true_positive, true_positive + false_negative)
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return precision, recall, f1


def _slice_reports(
    cases: list[CounterfactualCase],
    evaluations: list[CounterfactualCaseEvaluation],
    key_fn: Callable[[CounterfactualCase], str],
) -> dict[str, CounterfactualSliceMetrics]:
    grouped: dict[
        str,
        list[tuple[CounterfactualCase, CounterfactualCaseEvaluation]],
    ] = {}
    for case, evaluation in zip(cases, evaluations, strict=True):
        grouped.setdefault(key_fn(case), []).append((case, evaluation))
    return {
        key: _slice_metrics(items)
        for key, items in sorted(grouped.items())
    }


def _slice_metrics(
    items: list[tuple[CounterfactualCase, CounterfactualCaseEvaluation]],
) -> CounterfactualSliceMetrics:
    generated = len(items)
    detected = sum(evaluation.detected for _, evaluation in items)
    minimal = sum(case.minimality.passed for case, _ in items)
    valid = sum(
        case.minimality.passed and evaluation.detected
        for case, evaluation in items
    )
    return CounterfactualSliceMetrics(
        generated_case_count=generated,
        valid_case_count=valid,
        detected_case_count=detected,
        mutation_validity_rate=_rate(valid, generated),
        detection_rate=_rate(detected, generated),
        minimality_pass_rate=_rate(minimal, generated),
        mean_minimality_score=(
            mean(case.minimality_score for case, _ in items) if items else 0.0
        ),
        root_cause_f1=(
            mean(evaluation.root_f1 for _, evaluation in items) if items else 0.0
        ),
        failure_closure_f1=(
            mean(evaluation.closure_f1 for _, evaluation in items) if items else 0.0
        ),
    )


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0
