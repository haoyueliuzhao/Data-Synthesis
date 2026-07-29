from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from typing import Literal

from trusted_synthesis.core.evaluation.counterfactual.schema import (
    CounterfactualCalibrationReport,
    CounterfactualSliceMetrics,
)
from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.core.feedback import (
    FeedbackExposure,
    FeedbackRoute,
    FeedbackSignal,
)
from trusted_synthesis.core.task.schema import TaskPublicSpec
from trusted_synthesis.hashing import canonical_hash

from .schema import (
    CellFeedbackStatistics,
    ClauseFeedback,
    SynthesisCell,
    SynthesisPolicy,
    clause_feedback_id,
    synthesis_cell_id,
    synthesis_policy_id,
)

CLAUSE_CALIBRATION_FORMULA = (
    "geometric_mean(mutation_validity_rate,detection_rate,root_cause_f1,failure_closure_f1)"
)


def make_synthesis_cell(
    *,
    pattern_id: str,
    binding_stratum_id: str,
    difficulty_bucket: str,
    distractor_profile_id: str,
    declared_tightening_options: Mapping[str, Iterable[str]] | None = None,
    active_binding_constraints: Iterable[str] = (),
) -> SynthesisCell:
    options = {
        key: tuple(sorted(set(values)))
        for key, values in sorted((declared_tightening_options or {}).items())
    }
    active = tuple(sorted(set(active_binding_constraints)))
    provisional = SynthesisCell.model_construct(
        cell_id="pending",
        pattern_id=pattern_id,
        binding_stratum_id=binding_stratum_id,
        difficulty_bucket=difficulty_bucket,
        distractor_profile_id=distractor_profile_id,
        declared_tightening_options=options,
        active_binding_constraints=active,
    )
    return SynthesisCell(
        cell_id=synthesis_cell_id(provisional),
        pattern_id=pattern_id,
        binding_stratum_id=binding_stratum_id,
        difficulty_bucket=difficulty_bucket,
        distractor_profile_id=distractor_profile_id,
        declared_tightening_options=options,
        active_binding_constraints=active,
    )


def build_synthesis_cell(
    task: TaskPublicSpec,
    corpus: EvidenceCorpus,
    required_evidence_ids: Iterable[str],
    *,
    declared_tightening_options: Mapping[str, Iterable[str]] | None = None,
    active_binding_constraints: Iterable[str] = (),
) -> SynthesisCell:
    """Derive p/b/d/h without interpreting domain-specific field values."""

    required_ids = tuple(sorted(set(required_evidence_ids)))
    evidence_by_id = corpus.by_id()
    missing = tuple(
        evidence_id for evidence_id in required_ids if evidence_id not in evidence_by_id
    )
    if not required_ids or missing:
        raise ValueError(f"required evidence is absent from the corpus: {missing}")
    required = tuple(evidence_by_id[evidence_id] for evidence_id in required_ids)
    distractors = tuple(
        item for item in corpus.evidence if item.evidence_id not in set(required_ids)
    )
    pattern = task.metadata.get("task_pattern") or {}
    difficulty = task.metadata.get("difficulty_profile") or {}
    refinement = task.metadata.get("refinement_contract") or {}
    options = declared_tightening_options or refinement.get("tightening_options") or {}
    active = tuple(active_binding_constraints) or tuple(
        refinement.get("active_binding_constraints") or ()
    )
    pattern_id = str(pattern.get("pattern_id") or task.task_type)
    difficulty_bucket = str(difficulty.get("level") or pattern.get("difficulty_base") or "unknown")
    return make_synthesis_cell(
        pattern_id=pattern_id,
        binding_stratum_id=_binding_stratum_id(required),
        difficulty_bucket=difficulty_bucket,
        distractor_profile_id=_distractor_profile_id(required, distractors),
        declared_tightening_options=options,
        active_binding_constraints=active,
    )


def legacy_synthesis_cells(
    exposures: Iterable[FeedbackExposure],
) -> dict[str, SynthesisCell]:
    """Compatibility path for reports produced before synthesis cells were persisted."""

    by_task: dict[str, SynthesisCell] = {}
    for exposure in exposures:
        cell = make_synthesis_cell(
            pattern_id=exposure.pattern_id,
            binding_stratum_id="binding:unresolved",
            difficulty_bucket="unknown",
            distractor_profile_id="distractor:unresolved",
        )
        existing = by_task.get(exposure.task_id)
        if existing is not None and existing.cell_id != cell.cell_id:
            raise ValueError("one task cannot belong to multiple legacy synthesis cells")
        by_task[exposure.task_id] = cell
    return by_task


def clause_reliability(metrics: CounterfactualSliceMetrics) -> float:
    values = (
        metrics.mutation_validity_rate,
        metrics.detection_rate,
        metrics.root_cause_f1,
        metrics.failure_closure_f1,
    )
    if any(value <= 0 for value in values):
        return 0.0
    return math.prod(values) ** (1.0 / len(values))


def clause_calibration_from_metrics(
    metrics: Mapping[str, CounterfactualSliceMetrics],
) -> tuple[dict[str, float], str]:
    calibration = {
        clause_kind: clause_reliability(item) for clause_kind, item in sorted(metrics.items())
    }
    manifest_hash = canonical_hash(
        {
            "formula": CLAUSE_CALIBRATION_FORMULA,
            "metrics": metrics,
            "calibration": calibration,
        },
        prefix="clause_calibration_manifest:",
    )
    return calibration, manifest_hash


def clause_calibration_from_reports(
    reports: Iterable[CounterfactualCalibrationReport],
) -> tuple[dict[str, float], str]:
    report_items = tuple(reports)
    grouped: dict[str, list[CounterfactualSliceMetrics]] = defaultdict(list)
    for report in report_items:
        metrics_by_kind = (
            report.expected_root_clause_kind_metrics or report.source_clause_kind_metrics
        )
        for clause_kind, metrics in metrics_by_kind.items():
            grouped[clause_kind].append(metrics)
    combined = {
        clause_kind: _combine_slice_metrics(items) for clause_kind, items in sorted(grouped.items())
    }
    calibration, _ = clause_calibration_from_metrics(combined)
    manifest_hash = canonical_hash(
        {
            "formula": CLAUSE_CALIBRATION_FORMULA,
            "report_ids": tuple(sorted(report.calibration_id for report in report_items)),
            "combined_metrics": combined,
            "calibration": calibration,
        },
        prefix="clause_calibration_manifest:",
    )
    return calibration, manifest_hash


def calibrate_clause_feedback(
    signals: Iterable[FeedbackSignal],
    task_cells: Mapping[str, SynthesisCell],
    clause_calibration: Mapping[str, float],
    *,
    uncalibrated_reliability: float = 0.0,
    force_raw_reliability: bool = False,
) -> tuple[ClauseFeedback, ...]:
    if not 0 <= uncalibrated_reliability <= 1:
        raise ValueError("uncalibrated reliability must be between zero and one")
    by_id: dict[str, ClauseFeedback] = {}
    for signal in signals:
        cell = task_cells.get(signal.task_id)
        if cell is None:
            raise ValueError(f"feedback task has no synthesis cell: {signal.task_id}")
        has_calibration = signal.clause_kind in clause_calibration
        reliability = (
            1.0
            if force_raw_reliability
            else clause_calibration.get(signal.clause_kind, uncalibrated_reliability)
        )
        status: Literal["calibrated", "missing", "raw_ablation"] = (
            "raw_ablation"
            if force_raw_reliability
            else "calibrated"
            if has_calibration
            else "missing"
        )
        provisional = ClauseFeedback.model_construct(
            feedback_id="pending",
            source_signal_id=signal.signal_id,
            task_id=signal.task_id,
            cell_id=cell.cell_id,
            clause_id=signal.clause_id,
            clause_kind=signal.clause_kind,
            failure_family=signal.failure_family,
            route=signal.route,
            severity=signal.severity,
            severity_weight=signal.weight,
            calibration_reliability=reliability,
            calibrated_weight=signal.weight * reliability,
            calibration_status=status,
            failure_code=signal.failure_code,
        )
        item = ClauseFeedback(
            feedback_id=clause_feedback_id(provisional),
            source_signal_id=signal.signal_id,
            task_id=signal.task_id,
            cell_id=cell.cell_id,
            clause_id=signal.clause_id,
            clause_kind=signal.clause_kind,
            failure_family=signal.failure_family,
            route=signal.route,
            severity=signal.severity,
            severity_weight=signal.weight,
            calibration_reliability=reliability,
            calibrated_weight=signal.weight * reliability,
            calibration_status=status,
            failure_code=signal.failure_code,
        )
        by_id[item.feedback_id] = item
    return tuple(by_id[key] for key in sorted(by_id))


def build_observed_policy(
    task_cells: Mapping[str, SynthesisCell],
    *,
    target_probabilities: Mapping[str, float] | None = None,
    round_index: int = 0,
    label: str = "round_0_observed",
) -> SynthesisPolicy:
    if not task_cells:
        raise ValueError("an observed synthesis policy requires task cells")
    counts = Counter(cell.cell_id for cell in task_cells.values())
    total = sum(counts.values())
    probabilities = {key: value / total for key, value in sorted(counts.items())}
    targets = _normalize_distribution(target_probabilities or probabilities, set(counts))
    cells_by_id = _unique_cells(task_cells.values())
    cells = tuple(cells_by_id[key] for key in sorted(cells_by_id))
    provisional = SynthesisPolicy.model_construct(
        policy_id="pending",
        round_index=round_index,
        label=label,
        cells=cells,
        probabilities=probabilities,
        target_probabilities=targets,
        source_policy_id=None,
    )
    return SynthesisPolicy(
        policy_id=synthesis_policy_id(provisional),
        round_index=round_index,
        label=label,
        cells=cells,
        probabilities=probabilities,
        target_probabilities=targets,
        source_policy_id=None,
    )


def aggregate_cell_feedback(
    policy: SynthesisPolicy,
    exposures: Iterable[FeedbackExposure],
    feedback: Iterable[ClauseFeedback],
    task_cells: Mapping[str, SynthesisCell],
) -> tuple[CellFeedbackStatistics, ...]:
    explicit_exposure_tasks = {item.task_id for item in exposures}
    unknown_tasks = explicit_exposure_tasks - set(task_cells)
    if unknown_tasks:
        raise ValueError(f"feedback exposures have no synthesis cells: {sorted(unknown_tasks)}")
    exposed_by_cell: dict[str, set[str]] = defaultdict(set)
    for task_id in explicit_exposure_tasks:
        exposed_by_cell[task_cells[task_id].cell_id].add(task_id)
    total_exposures = len(explicit_exposure_tasks)
    feedback_by_cell: dict[str, list[ClauseFeedback]] = defaultdict(list)
    for item in feedback:
        if item.task_id not in explicit_exposure_tasks:
            raise ValueError(f"clause feedback has no task exposure: {item.task_id}")
        expected_cell_id = task_cells[item.task_id].cell_id
        if item.cell_id != expected_cell_id:
            raise ValueError(
                "clause feedback cell does not match its task binding: "
                f"{item.task_id} expected {expected_cell_id}, observed {item.cell_id}"
            )
        feedback_by_cell[item.cell_id].append(item)
    statistics = []
    for cell in policy.cells:
        items = feedback_by_cell.get(cell.cell_id, [])
        exposure_count = len(exposed_by_cell.get(cell.cell_id, set()))
        defect_weight = sum(
            item.calibrated_weight
            for item in items
            if item.route == FeedbackRoute.UPSTREAM_DATA_DEFECT
        )
        capability_weight = sum(
            item.calibrated_weight
            for item in items
            if item.route == FeedbackRoute.AGENT_CAPABILITY_GAP
        )
        interface_weight = sum(
            item.calibrated_weight
            for item in items
            if item.route == FeedbackRoute.INTERFACE_FAILURE
        )
        observed = exposure_count / total_exposures if total_exposures else 0.0
        target = policy.target_probabilities[cell.cell_id]
        statistics.append(
            CellFeedbackStatistics(
                cell_id=cell.cell_id,
                exposure_count=exposure_count,
                root_feedback_count=len(items),
                interface_failure_count=sum(
                    item.route == FeedbackRoute.INTERFACE_FAILURE for item in items
                ),
                synthesis_defect_count=sum(
                    item.route == FeedbackRoute.UPSTREAM_DATA_DEFECT for item in items
                ),
                capability_gap_count=sum(
                    item.route == FeedbackRoute.AGENT_CAPABILITY_GAP for item in items
                ),
                uncalibrated_feedback_count=sum(
                    item.calibration_status == "missing" for item in items
                ),
                interface_weight_sum=interface_weight,
                synthesis_defect_weight_sum=defect_weight,
                capability_gap_weight_sum=capability_weight,
                synthesis_defect_risk=(defect_weight / exposure_count if exposure_count else 0.0),
                capability_gap_demand=(
                    capability_weight / exposure_count if exposure_count else 0.0
                ),
                target_share=target,
                observed_share=observed,
                coverage_gap=max(0.0, target - observed),
            )
        )
    return tuple(sorted(statistics, key=lambda item: item.cell_id))


def _binding_stratum_id(evidence: tuple[EvidenceItem, ...]) -> str:
    definitions = sum(
        bool(item.definition.definition_id or item.definition.text) for item in evidence
    )
    structure = {
        "evidence_count_bucket": _count_bucket(len(evidence)),
        "evidence_kinds": tuple(sorted({item.evidence_kind.value for item in evidence})),
        "source_authorities": tuple(sorted({item.source.authority.value for item in evidence})),
        "source_count_bucket": _count_bucket(len({item.source.source_id for item in evidence})),
        "definition_coverage": _coverage_label(definitions, len(evidence)),
        "temporal_basis_cardinality": len(
            {item.temporal_context.basis for item in evidence if item.temporal_context.basis}
        ),
        "frequency_cardinality": len(
            {
                item.temporal_context.frequency
                for item in evidence
                if item.temporal_context.frequency
            }
        ),
        "scope_types": tuple(
            sorted({item.scope.scope_type for item in evidence if item.scope is not None})
        ),
    }
    return canonical_hash(structure, prefix="binding_stratum:")


def _distractor_profile_id(
    required: tuple[EvidenceItem, ...],
    distractors: tuple[EvidenceItem, ...],
) -> str:
    if not distractors:
        return "distractor:none"
    signatures = Counter(_closest_distractor_signature(item, required) for item in distractors)
    structure = {
        "count_bucket": _count_bucket(len(distractors)),
        "signatures": tuple(sorted(signatures.items())),
    }
    return canonical_hash(structure, prefix="distractor_profile:")


def _closest_distractor_signature(
    distractor: EvidenceItem,
    required: tuple[EvidenceItem, ...],
) -> str:
    signatures = []
    for item in required:
        signatures.append(
            (
                int(distractor.subject.subject_id == item.subject.subject_id),
                int(distractor.predicate == item.predicate),
                int(distractor.definition.definition_id == item.definition.definition_id),
                int(
                    (distractor.scope.scope_id if distractor.scope else None)
                    == (item.scope.scope_id if item.scope else None)
                ),
                int(distractor.temporal_context.label == item.temporal_context.label),
                int(distractor.source.source_id == item.source.source_id),
            )
        )
    return "".join(str(value) for value in max(signatures))


def _combine_slice_metrics(
    values: list[CounterfactualSliceMetrics],
) -> CounterfactualSliceMetrics:
    generated = sum(item.generated_case_count for item in values)
    valid = sum(item.valid_case_count for item in values)
    detected = sum(item.detected_case_count for item in values)

    def weighted(field: str) -> float:
        if generated == 0:
            return 0.0
        return sum(getattr(item, field) * item.generated_case_count for item in values) / generated

    return CounterfactualSliceMetrics(
        generated_case_count=generated,
        valid_case_count=valid,
        detected_case_count=detected,
        mutation_validity_rate=valid / generated if generated else 0.0,
        detection_rate=detected / generated if generated else 0.0,
        minimality_pass_rate=weighted("minimality_pass_rate"),
        mean_minimality_score=weighted("mean_minimality_score"),
        root_cause_f1=weighted("root_cause_f1"),
        failure_closure_f1=weighted("failure_closure_f1"),
    )


def _normalize_distribution(
    values: Mapping[str, float],
    expected_keys: set[str],
) -> dict[str, float]:
    if set(values) != expected_keys:
        raise ValueError("target distribution must cover exactly the observed cells")
    if any(value < 0 for value in values.values()):
        raise ValueError("target distribution cannot contain negative values")
    total = sum(values.values())
    if total <= 0:
        raise ValueError("target distribution must have positive mass")
    return {key: values[key] / total for key in sorted(values)}


def _unique_cells(values: Iterable[SynthesisCell]) -> dict[str, SynthesisCell]:
    cells: dict[str, SynthesisCell] = {}
    for value in values:
        existing = cells.get(value.cell_id)
        if existing is not None and existing != value:
            raise ValueError("one synthesis cell ID resolved to conflicting declarations")
        cells[value.cell_id] = value
    return cells


def _count_bucket(value: int) -> str:
    if value <= 1:
        return "1"
    if value == 2:
        return "2"
    if value <= 5:
        return "3_5"
    if value <= 10:
        return "6_10"
    return "11_plus"


def _coverage_label(count: int, total: int) -> str:
    if count == 0:
        return "none"
    if count == total:
        return "complete"
    return "partial"
