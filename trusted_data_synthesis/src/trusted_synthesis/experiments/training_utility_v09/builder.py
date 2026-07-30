from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from statistics import mean
from typing import Literal

from trusted_synthesis.core.evaluation.counterfactual import (
    CounterfactualCalibrationReport,
)
from trusted_synthesis.core.feedback import (
    FeedbackExposure,
    FeedbackRoute,
    FeedbackSignal,
    aggregate_pattern_clause_failures,
    allocate_refinement_budget,
)
from trusted_synthesis.core.refinement import (
    CLAUSE_CALIBRATION_FORMULA,
    CellFeedbackStatistics,
    SynthesisCell,
    aggregate_cell_feedback,
    build_observed_policy,
    calibrate_clause_feedback,
    clause_calibration_from_reports,
    legacy_synthesis_cells,
    random_same_shift_update,
    update_synthesis_policy,
)
from trusted_synthesis.experiments.agent_validation.schema import AgentValidationReport
from trusted_synthesis.hashing import canonical_hash

from .schema import (
    V09Cohort,
    V09CohortContract,
    V09ExperimentAxis,
    V09OnlineGate,
    V09RefinementConfig,
    V09RefinementManifest,
)


def compile_v09_refinement(
    config: V09RefinementConfig,
    *,
    exposures: tuple[FeedbackExposure, ...],
    signals: tuple[FeedbackSignal, ...],
    feedback_source: str,
    round0_real_agent_feedback: bool,
    online_gate: V09OnlineGate | None = None,
    task_cells: Mapping[str, SynthesisCell] | None = None,
    clause_calibration: Mapping[str, float] | None = None,
    calibration_manifest_hash: str | None = None,
    target_probabilities: Mapping[str, float] | None = None,
    task_domains: Mapping[str, str] | None = None,
    task_quality_scores: Mapping[str, float],
    quality_score_policy_hash: str,
    quality_score_source: str,
) -> V09RefinementManifest:
    exposure_items = tuple(exposures)
    resolved_cells = dict(task_cells or legacy_synthesis_cells(exposure_items))
    if set(item.task_id for item in exposure_items) - set(resolved_cells):
        raise ValueError("every feedback exposure requires a synthesis cell")
    exposure_domains: dict[str, str] = {}
    for item in exposure_items:
        previous = exposure_domains.setdefault(item.task_id, item.domain)
        if previous != item.domain:
            raise ValueError("one feedback task cannot span domains")
    resolved_domains = dict(task_domains or exposure_domains)
    if set(resolved_domains) != set(resolved_cells):
        raise ValueError("task domains must cover every synthesis Cell task")
    training_domains = {domain for domain, weight in config.domain_weights.items() if weight > 0}
    policy_task_ids = {
        task_id for task_id, domain in resolved_domains.items() if domain in training_domains
    }
    if not policy_task_ids:
        raise ValueError("feedback contains no task in the frozen primary training domain")
    policy_cells = {task_id: resolved_cells[task_id] for task_id in sorted(policy_task_ids)}
    policy_domains = {task_id: resolved_domains[task_id] for task_id in sorted(policy_task_ids)}
    policy_exposures = tuple(item for item in exposure_items if item.task_id in policy_task_ids)
    policy_signals = tuple(item for item in signals if item.task_id in policy_task_ids)
    resolved_quality_scores = {
        task_id: float(score) for task_id, score in sorted(task_quality_scores.items())
    }
    if set(resolved_quality_scores) != policy_task_ids:
        raise ValueError("scalar quality scores must cover exactly the refinement tasks")
    if any(not 0 <= score <= 1 for score in resolved_quality_scores.values()):
        raise ValueError("scalar quality scores must be in [0, 1]")
    if not quality_score_policy_hash or not quality_score_source:
        raise ValueError("scalar quality scores require source and policy identities")
    score_manifest_hash = canonical_hash(
        {
            "source": quality_score_source,
            "policy_hash": quality_score_policy_hash,
            "task_scores": resolved_quality_scores,
            "task_cell_ids": {
                task_id: policy_cells[task_id].cell_id for task_id in sorted(policy_cells)
            },
        },
        prefix="training_utility_v09_scalar_quality_manifest:",
    )
    cell_groups = _cell_conditioning_groups(policy_cells, policy_domains)
    represented_weights = _represented_group_weights(
        cell_groups,
        config.domain_weights,
    )
    unique_cells = {cell.cell_id: cell for cell in policy_cells.values()}
    pattern_catalog_hash = canonical_hash(
        tuple(sorted({item.pattern_id for item in unique_cells.values()})),
        prefix="training_utility_v09_pattern_catalog:",
    )
    cohort_contracts = _cohort_contracts(config, pattern_catalog_hash)
    failures = aggregate_pattern_clause_failures(policy_exposures, policy_signals)
    capability_count = sum(
        item.route == FeedbackRoute.AGENT_CAPABILITY_GAP for item in policy_signals
    )
    allocations = (
        tuple(
            allocate_refinement_budget(
                failures,
                total_budget=config.cohort_example_budget,
                lambda_value=lambda_value,
                alpha=config.alpha,
                epsilon=config.epsilon,
                capability_signal_count=capability_count,
            )
            for lambda_value in config.lambda_values
        )
        if failures
        else ()
    )
    primary = next(
        (item for item in allocations if item.lambda_value == config.primary_lambda),
        None,
    )
    calibration = dict(sorted((clause_calibration or {}).items()))
    resolved_calibration_hash = calibration_manifest_hash or canonical_hash(
        {
            "formula": CLAUSE_CALIBRATION_FORMULA,
            "calibration": calibration,
            "status": "caller_did_not_supply_calibration_manifest",
        },
        prefix="clause_calibration_manifest:",
    )
    prior_policy = build_observed_policy(
        policy_cells,
        target_probabilities=_restrict_target_probabilities(
            target_probabilities,
            {item.cell_id for item in policy_cells.values()},
        ),
        task_groups=policy_domains,
        fixed_group_weights=represented_weights,
    )
    calibrated_feedback = calibrate_clause_feedback(
        policy_signals,
        policy_cells,
        calibration,
        uncalibrated_reliability=config.ccgr_uncalibrated_reliability,
    )
    raw_feedback = calibrate_clause_feedback(
        policy_signals,
        policy_cells,
        calibration,
        force_raw_reliability=True,
    )
    calibrated_statistics = aggregate_cell_feedback(
        prior_policy,
        policy_exposures,
        calibrated_feedback,
        policy_cells,
        minimum_cell_exposure=config.ccgr_minimum_cell_exposure,
        shrinkage_strength=config.ccgr_pattern_shrinkage_strength,
        normalize_root_mass=config.ccgr_normalize_root_mass,
    )
    raw_statistics = aggregate_cell_feedback(
        prior_policy,
        policy_exposures,
        raw_feedback,
        policy_cells,
        minimum_cell_exposure=config.ccgr_minimum_cell_exposure,
        shrinkage_strength=config.ccgr_pattern_shrinkage_strength,
        normalize_root_mass=config.ccgr_normalize_root_mass,
    )
    static = update_synthesis_policy(
        prior_policy,
        calibrated_statistics,
        calibrated_feedback,
        eta=0.0,
        beta=config.ccgr_beta,
        gamma=config.ccgr_gamma,
        total_budget=config.cohort_example_budget,
        calibration_manifest_hash=resolved_calibration_hash,
        binding_tightening_threshold=config.ccgr_binding_tightening_threshold,
        ablation_id="static_verified",
        enable_binding_tightening=False,
        require_calibrated_feedback=False,
        conditioning_groups=cell_groups,
        fixed_group_weights=represented_weights,
    )
    raw = update_synthesis_policy(
        prior_policy,
        raw_statistics,
        raw_feedback,
        eta=config.ccgr_eta,
        beta=config.ccgr_beta,
        gamma=config.ccgr_gamma,
        total_budget=config.cohort_example_budget,
        calibration_manifest_hash=resolved_calibration_hash,
        binding_tightening_threshold=config.ccgr_binding_tightening_threshold,
        ablation_id="raw_failure_reweighting",
        conditioning_groups=cell_groups,
        fixed_group_weights=represented_weights,
    )
    score_only_utilities = _score_only_cell_utilities(
        calibrated_statistics,
        task_quality_scores=resolved_quality_scores,
        task_cell_ids={task_id: policy_cells[task_id].cell_id for task_id in sorted(policy_cells)},
        gamma=config.ccgr_gamma,
    )
    score_only = update_synthesis_policy(
        prior_policy,
        calibrated_statistics,
        (),
        eta=config.ccgr_eta,
        beta=0.0,
        gamma=config.ccgr_gamma,
        total_budget=config.cohort_example_budget,
        calibration_manifest_hash=score_manifest_hash,
        binding_tightening_threshold=config.ccgr_binding_tightening_threshold,
        ablation_id="score_only_feedback",
        enable_binding_tightening=False,
        require_calibrated_feedback=False,
        utility_overrides=score_only_utilities,
        utility_mode="score_only_control",
        conditioning_groups=cell_groups,
        fixed_group_weights=represented_weights,
    )
    no_defect = update_synthesis_policy(
        prior_policy,
        calibrated_statistics,
        calibrated_feedback,
        eta=config.ccgr_eta,
        beta=0.0,
        gamma=config.ccgr_gamma,
        total_budget=config.cohort_example_budget,
        calibration_manifest_hash=resolved_calibration_hash,
        binding_tightening_threshold=config.ccgr_binding_tightening_threshold,
        ablation_id="no_defect_suppression",
        conditioning_groups=cell_groups,
        fixed_group_weights=represented_weights,
    )
    no_coverage = update_synthesis_policy(
        prior_policy,
        calibrated_statistics,
        calibrated_feedback,
        eta=config.ccgr_eta,
        beta=config.ccgr_beta,
        gamma=0.0,
        total_budget=config.cohort_example_budget,
        calibration_manifest_hash=resolved_calibration_hash,
        binding_tightening_threshold=config.ccgr_binding_tightening_threshold,
        ablation_id="no_coverage_regularization",
        conditioning_groups=cell_groups,
        fixed_group_weights=represented_weights,
    )
    full = update_synthesis_policy(
        prior_policy,
        calibrated_statistics,
        calibrated_feedback,
        eta=config.ccgr_eta,
        beta=config.ccgr_beta,
        gamma=config.ccgr_gamma,
        total_budget=config.cohort_example_budget,
        calibration_manifest_hash=resolved_calibration_hash,
        binding_tightening_threshold=config.ccgr_binding_tightening_threshold,
        ablation_id="full_ccgr",
        conditioning_groups=cell_groups,
        fixed_group_weights=represented_weights,
    )
    random_control = random_same_shift_update(
        prior_policy,
        calibrated_statistics,
        reference_update=full,
        total_budget=config.cohort_example_budget,
        calibration_manifest_hash=resolved_calibration_hash,
        random_seed=config.random_seed,
    )
    ccgr_updates = (
        static,
        score_only,
        raw,
        no_defect,
        no_coverage,
        random_control,
        full,
    )
    calibrated_kinds = {
        item.clause_kind for item in calibrated_feedback if item.calibration_status == "calibrated"
    }
    observed_kinds = {item.clause_kind for item in calibrated_feedback}
    calibration_coverage = len(calibrated_kinds) / len(observed_kinds) if observed_kinds else 0.0
    gate = online_gate or V09OnlineGate(status="not_run")
    status: Literal["initial_ready", "ready_for_online_gate", "blocked"]
    if not failures or full.status == "blocked":
        status = "blocked"
    elif gate.status == "passed" and round0_real_agent_feedback:
        status = "initial_ready"
    else:
        status = "ready_for_online_gate"
    limitations = (
        "Capability gaps increase clean training demand; synthesis defects suppress cells.",
        "Interface failures repair prompts/runtime and have zero synthesis utility.",
        "Uncalibrated clauses are fail-closed at the configured reliability floor.",
        "Binding tightening can only activate options predeclared by a plugin or pattern.",
        "Refinement cannot add patterns, operators, contracts, or agent strategies.",
        "Score-only, random-same-shift, and raw-feedback policies are manifest-only "
        "controls until equal-token cohorts are materialized; only C3 versus C4 is identified.",
        "Selected=used=cited evidence remains a controlled-task assumption.",
        "External native benchmarks have not been executed.",
        *(
            ()
            if round0_real_agent_feedback
            else ("Offline typed counterfactual feedback is not a real-agent Round-0 result.",)
        ),
        *(
            ()
            if any(item.route == FeedbackRoute.UPSTREAM_DATA_DEFECT for item in calibrated_feedback)
            else (
                "This feedback slice contains no synthesis-defect root; beta is not "
                "empirically identified by this run.",
            )
        ),
        *(
            ()
            if calibration_coverage == 1.0
            else ("Uncalibrated observed root Clause kinds retain zero refinement weight.",)
        ),
    )
    route_counts = Counter(item.route.value for item in signals)
    validation_domain_exposure_counts = Counter(item.domain for item in exposure_items)
    validation_domain_signal_counts = Counter(item.domain for item in signals)
    refinement_domain_exposure_counts = Counter(item.domain for item in policy_exposures)
    refinement_domain_signal_counts = Counter(item.domain for item in policy_signals)
    experiment_axes = _experiment_axes()
    identity = {
        "experiment_protocol_id": config.experiment_protocol_id,
        "research_question_ids": config.research_question_ids,
        "primary_training_domain": config.primary_training_domain,
        "cross_domain_validation_domains": config.cross_domain_validation_domains,
        "validation_task_ids": tuple(sorted(resolved_cells)),
        "validation_domain_exposure_counts": validation_domain_exposure_counts,
        "validation_domain_signal_counts": validation_domain_signal_counts,
        "refinement_task_ids": tuple(sorted(policy_task_ids)),
        "refinement_domain_exposure_counts": refinement_domain_exposure_counts,
        "refinement_domain_signal_counts": refinement_domain_signal_counts,
        "score_only_quality_source": quality_score_source,
        "score_only_quality_policy_hash": quality_score_policy_hash,
        "score_only_quality_manifest_hash": score_manifest_hash,
        "config_hash": config.config_hash,
        "feedback_source": feedback_source,
        "round0_real_agent_feedback": round0_real_agent_feedback,
        "exposures": exposure_items,
        "signals": signals,
        "allocations": allocations,
        "synthesis_cells": tuple(unique_cells.values()),
        "clause_feedback": calibrated_feedback,
        "ccgr_updates": ccgr_updates,
        "experiment_axes": experiment_axes,
        "online_gate": gate,
        "cohorts": cohort_contracts,
    }
    return V09RefinementManifest(
        manifest_id=canonical_hash(identity, prefix="training_utility_v09_manifest:"),
        experiment_protocol_id=config.experiment_protocol_id,
        research_question_ids=config.research_question_ids,
        primary_training_domain=config.primary_training_domain,
        cross_domain_validation_domains=config.cross_domain_validation_domains,
        engineering_regression_cohort_ids=config.engineering_regression_cohort_ids,
        config_hash=config.config_hash,
        pattern_catalog_hash=pattern_catalog_hash,
        feedback_source=feedback_source,
        round0_real_agent_feedback=round0_real_agent_feedback,
        feedback_exposure_count=len(exposure_items),
        feedback_signal_count=len(signals),
        feedback_route_counts=dict(sorted(route_counts.items())),
        validation_task_ids=tuple(sorted(resolved_cells)),
        validation_exposure_count=len(exposure_items),
        validation_signal_count=len(signals),
        validation_domain_exposure_counts=dict(sorted(validation_domain_exposure_counts.items())),
        validation_domain_signal_counts=dict(sorted(validation_domain_signal_counts.items())),
        refinement_task_ids=tuple(sorted(policy_task_ids)),
        refinement_exposure_count=len(policy_exposures),
        refinement_signal_count=len(policy_signals),
        refinement_domain_exposure_counts=dict(sorted(refinement_domain_exposure_counts.items())),
        refinement_domain_signal_counts=dict(sorted(refinement_domain_signal_counts.items())),
        score_only_quality_source=quality_score_source,
        score_only_quality_score_count=len(resolved_quality_scores),
        score_only_quality_policy_hash=quality_score_policy_hash,
        score_only_quality_manifest_hash=score_manifest_hash,
        pattern_clause_failures=failures,
        allocations=allocations,
        primary_allocation_id=primary.allocation_id if primary is not None else None,
        synthesis_cells=tuple(unique_cells[key] for key in sorted(unique_cells)),
        clause_feedback=calibrated_feedback,
        clause_calibration=calibration,
        calibration_manifest_hash=resolved_calibration_hash,
        calibration_coverage_rate=calibration_coverage,
        ccgr_updates=ccgr_updates,
        primary_ccgr_update_id=full.update_id,
        experiment_axes=experiment_axes,
        cohort_contracts=cohort_contracts,
        online_gate=gate,
        limitations=limitations,
        status=status,
    )


def compile_v09_from_agent_report(
    config: V09RefinementConfig,
    report: AgentValidationReport,
    *,
    resume_completed_api_call_count: int | None = None,
    calibration_reports: Iterable[CounterfactualCalibrationReport] = (),
    target_probabilities: Mapping[str, float] | None = None,
) -> V09RefinementManifest:
    exposures = tuple(
        exposure for sample in report.samples for exposure in sample.feedback_exposures
    )
    signals = tuple(signal for sample in report.samples for signal in sample.feedback_signals)
    task_cells = {
        sample.task_id: sample.synthesis_cell
        for sample in report.samples
        if sample.synthesis_cell is not None
    }
    task_domains = {
        sample.task_id: sample.domain
        for sample in report.samples
        if sample.synthesis_cell is not None
    }
    resolved_targets = target_probabilities or _domain_weighted_targets(
        task_cells,
        task_domains,
        config.domain_weights,
    )
    calibration, calibration_hash = clause_calibration_from_reports(
        calibration_reports,
        confidence_prior_count=config.ccgr_clause_confidence_prior_count,
    )
    requested = sum(report.requested_domain_candidate_counts.values())
    accepted_samples = tuple(
        item
        for item in report.samples
        if item.contract_assessment is not None
        and item.contract_assessment.decision.value == "accepted"
    )
    accepted_domains = tuple(sorted({item.domain for item in accepted_samples}))
    accepted_patterns = tuple(sorted({item.pattern_id for item in accepted_samples}))
    expected_patterns = set(report.pattern_counts)
    failures: list[str] = []
    attempted_rate = report.attempted_count / requested if requested else 0.0
    checks = {
        "attempted_rate_lt_1": attempted_rate < 1.0,
        "action_plan_contract_rate_below_contract": (
            report.action_plan_contract_success_rate
            < config.online_minimum_action_plan_contract_rate
        ),
        "host_execution_evaluable_rate_below_contract": (
            report.host_execution_evaluable_rate
            < config.online_minimum_host_execution_evaluable_rate
        ),
        "answer_decision_contract_rate_below_contract": (
            report.answer_decision_contract_success_rate
            < config.online_minimum_answer_decision_contract_rate
        ),
        "contract_acceptance_rate_below_contract": (
            report.contract_acceptance_rate < config.online_minimum_contract_acceptance_rate
        ),
        "accepted_domain_missing": set(accepted_domains) != {"finance", "legal", "science"},
        "accepted_pattern_missing": set(accepted_patterns) != expected_patterns,
        "resume_reused_task_called_api": (
            resume_completed_api_call_count is not None and resume_completed_api_call_count != 0
        ),
    }
    failures.extend(key for key, failed in checks.items() if failed)
    gate = V09OnlineGate(
        attempted_rate=attempted_rate,
        action_plan_contract_rate=report.action_plan_contract_success_rate,
        host_execution_evaluable_rate=report.host_execution_evaluable_rate,
        answer_decision_contract_rate=report.answer_decision_contract_success_rate,
        contract_acceptance_rate=report.contract_acceptance_rate,
        accepted_domains=accepted_domains,
        accepted_patterns=accepted_patterns,
        first_call_action_success_count=report.action_first_call_success_count,
        repaired_action_success_count=report.action_repaired_success_count,
        first_call_answer_success_count=report.answer_first_call_success_count,
        repaired_answer_success_count=report.answer_repaired_success_count,
        resume_completed_api_call_count=resume_completed_api_call_count,
        failures=tuple(failures),
        status="passed" if not failures else "failed",
    )
    refinement_quality_samples = tuple(
        item
        for item in report.samples
        if item.task_id in task_cells
        and task_domains[item.task_id] == config.primary_training_domain
    )
    if any(item.quality_vector is None for item in refinement_quality_samples):
        raise ValueError("every Finance refinement sample requires a QualityVector")
    quality_scores = {
        item.task_id: item.quality_vector.overall_score
        for item in refinement_quality_samples
        if item.quality_vector is not None
    }
    if len(quality_scores) != len(refinement_quality_samples):
        raise ValueError("one scalar quality score is required per Finance refinement task")
    quality_policy_hashes = {
        item.quality_vector.policy_hash
        for item in refinement_quality_samples
        if item.quality_vector is not None
    }
    if len(quality_policy_hashes) != 1:
        raise ValueError("Finance score-only feedback requires one QualityVector policy")
    return compile_v09_refinement(
        config,
        exposures=exposures,
        signals=signals,
        feedback_source=report.run_id,
        round0_real_agent_feedback=True,
        online_gate=gate,
        task_cells=task_cells or None,
        clause_calibration=calibration,
        calibration_manifest_hash=calibration_hash,
        target_probabilities=resolved_targets or None,
        task_domains=task_domains or None,
        task_quality_scores=quality_scores,
        quality_score_policy_hash=next(iter(quality_policy_hashes)),
        quality_score_source=(
            f"{report.run_id}:AgentValidationSample.quality_vector.overall_score"
        ),
    )


def _experiment_axes() -> tuple[V09ExperimentAxis, ...]:
    return (
        V09ExperimentAxis(
            axis_id="co_compilation",
            members=(
                V09Cohort.CONVENTIONAL_SYNTHETIC.value,
                V09Cohort.EVIDENCE_GROUNDED.value,
                V09Cohort.VERIFIED_STATIC.value,
            ),
            primary_contrast=(
                V09Cohort.EVIDENCE_GROUNDED.value,
                V09Cohort.VERIFIED_STATIC.value,
            ),
            causal_status="exploratory",
            controlled_variables=("base_model", "training_seed", "supervised_token_budget"),
            unresolved_confounds=(
                "program_visibility",
                "planning_track",
                "task_pool",
                "proof_contract",
                "teacher_target_source",
            ),
        ),
        V09ExperimentAxis(
            axis_id="ccgr_refinement",
            members=(
                V09Cohort.VERIFIED_STATIC.value,
                V09Cohort.FEEDBACK_REFINED.value,
            ),
            primary_contrast=(
                V09Cohort.VERIFIED_STATIC.value,
                V09Cohort.FEEDBACK_REFINED.value,
            ),
            causal_status="identified",
            controlled_variables=(
                "base_model",
                "training_seed",
                "supervised_token_budget",
                "fixed_group_marginals",
                "compiler_contract",
                "candidate_superpool",
            ),
        ),
    )


def _cell_conditioning_groups(
    task_cells: Mapping[str, SynthesisCell],
    task_groups: Mapping[str, str],
) -> dict[str, str]:
    groups: dict[str, str] = {}
    for task_id, cell in task_cells.items():
        group = task_groups[task_id]
        previous = groups.setdefault(cell.cell_id, group)
        if previous != group:
            raise ValueError("one synthesis Cell cannot span conditioning groups")
    return dict(sorted(groups.items()))


def _represented_group_weights(
    cell_groups: Mapping[str, str],
    configured_weights: Mapping[str, float],
) -> dict[str, float]:
    groups = set(cell_groups.values())
    missing = groups - set(configured_weights)
    if missing:
        raise ValueError(f"conditioning groups have no configured weights: {sorted(missing)}")
    total = sum(configured_weights[group] for group in groups)
    if total <= 0:
        raise ValueError("represented conditioning groups require positive weight")
    return {group: configured_weights[group] / total for group in sorted(groups)}


def _cohort_contracts(
    config: V09RefinementConfig,
    pattern_catalog_hash: str,
) -> tuple[V09CohortContract, ...]:
    def make_contract(
        cohort: V09Cohort,
        *,
        evidence_grounded: bool,
        proof_graph_required: bool,
        executable_program_contract: bool,
        quality_contract_required: bool,
        feedback_refined: bool,
    ) -> V09CohortContract:
        return V09CohortContract(
            cohort=cohort,
            base_model=config.base_model,
            base_model_revision=config.base_model_revision,
            training_seed=config.training_seed,
            pattern_catalog_hash=pattern_catalog_hash,
            evidence_grounded=evidence_grounded,
            proof_graph_required=proof_graph_required,
            executable_program_contract=executable_program_contract,
            quality_contract_required=quality_contract_required,
            feedback_refined=feedback_refined,
            training_format=config.student_training_format,
            supervised_token_budget=config.supervised_token_budget,
            domain_weights=config.domain_weights,
        )

    return (
        make_contract(
            V09Cohort.CONVENTIONAL_SYNTHETIC,
            evidence_grounded=False,
            proof_graph_required=False,
            executable_program_contract=False,
            quality_contract_required=False,
            feedback_refined=False,
        ),
        make_contract(
            V09Cohort.EVIDENCE_GROUNDED,
            evidence_grounded=True,
            proof_graph_required=False,
            executable_program_contract=False,
            quality_contract_required=False,
            feedback_refined=False,
        ),
        make_contract(
            V09Cohort.VERIFIED_STATIC,
            evidence_grounded=True,
            proof_graph_required=True,
            executable_program_contract=True,
            quality_contract_required=True,
            feedback_refined=False,
        ),
        make_contract(
            V09Cohort.FEEDBACK_REFINED,
            evidence_grounded=True,
            proof_graph_required=True,
            executable_program_contract=True,
            quality_contract_required=True,
            feedback_refined=True,
        ),
    )


def _domain_weighted_targets(
    task_cells: Mapping[str, SynthesisCell],
    task_domains: Mapping[str, str],
    domain_weights: Mapping[str, float],
) -> dict[str, float]:
    if not task_cells:
        return {}
    counts = Counter((task_domains[task_id], cell.cell_id) for task_id, cell in task_cells.items())
    domain_totals = Counter(task_domains.values())
    targets: dict[str, float] = defaultdict(float)
    for (domain, cell_id), count in counts.items():
        targets[cell_id] += domain_weights.get(domain, 0.0) * count / domain_totals[domain]
    return dict(sorted(targets.items()))


def _restrict_target_probabilities(
    target_probabilities: Mapping[str, float] | None,
    cell_ids: set[str],
) -> dict[str, float] | None:
    if target_probabilities is None:
        return None
    selected = {
        cell_id: float(target_probabilities.get(cell_id, 0.0)) for cell_id in sorted(cell_ids)
    }
    total = sum(selected.values())
    if total <= 0:
        raise ValueError("primary training Cells require positive target probability")
    return {cell_id: value / total for cell_id, value in selected.items()}


def _score_only_cell_utilities(
    statistics: Iterable[CellFeedbackStatistics],
    *,
    task_quality_scores: Mapping[str, float],
    task_cell_ids: Mapping[str, str],
    gamma: float,
) -> dict[str, float]:
    """Use mean scalar Agent quality per Cell without Clause or route semantics."""

    if gamma < 0:
        raise ValueError("score-only coverage weight cannot be negative")
    if set(task_quality_scores) != set(task_cell_ids):
        raise ValueError("score-only task scores and Cell bindings must match")
    scores_by_cell: dict[str, list[float]] = defaultdict(list)
    for task_id, score in sorted(task_quality_scores.items()):
        if not 0 <= score <= 1:
            raise ValueError("score-only task quality must be in [0, 1]")
        scores_by_cell[task_cell_ids[task_id]].append(float(score))
    statistics_by_cell = {item.cell_id: item for item in statistics}
    if set(scores_by_cell) != set(statistics_by_cell):
        raise ValueError("score-only quality must cover every policy Cell")
    return {
        cell_id: (-(1.0 - mean(scores_by_cell[cell_id])) + gamma * item.coverage_gap)
        for cell_id, item in sorted(statistics_by_cell.items())
    }


def write_v09_real_refinement_artifacts(
    output_dir: Path,
    manifest: V09RefinementManifest,
    report: AgentValidationReport,
) -> None:
    """Freeze online CCGR inputs and outputs as a replayable artifact set."""

    output_dir.mkdir(parents=True, exist_ok=True)
    exposures = tuple(item for sample in report.samples for item in sample.feedback_exposures)
    signals = tuple(item for sample in report.samples for item in sample.feedback_signals)
    _write_refinement_json(output_dir / "v09_refinement_manifest.json", manifest)
    _write_refinement_json(output_dir / "online_gate.json", manifest.online_gate)
    _write_refinement_json(output_dir / "ccgr_policy_updates.json", manifest.ccgr_updates)
    _write_refinement_jsonl(output_dir / "feedback_exposures.jsonl", exposures)
    _write_refinement_jsonl(output_dir / "feedback_signals.jsonl", signals)
    _write_refinement_jsonl(output_dir / "synthesis_cells.jsonl", manifest.synthesis_cells)
    _write_refinement_jsonl(output_dir / "clause_feedback.jsonl", manifest.clause_feedback)
    summary = {
        "version": "v09_real_refinement_artifacts.v1",
        "source_agent_run_id": report.run_id,
        "source_agent_report_hash": report.report_hash,
        "finance_task_source": report.finance_task_source,
        "finance_archive_kg_build_id": report.finance_archive_kg_build_id,
        "task_source_manifest_hash": report.task_source_manifest_hash,
        "refinement_manifest_id": manifest.manifest_id,
        "refinement_manifest_hash": canonical_hash(
            manifest,
            prefix="v09_refinement_manifest_content:",
        ),
        "online_gate_status": manifest.online_gate.status,
        "feedback_exposure_count": len(exposures),
        "feedback_signal_count": len(signals),
        "synthesis_cell_count": len(manifest.synthesis_cells),
        "status": manifest.status,
    }
    _write_refinement_json(output_dir / "real_refinement_summary.json", summary)


def _refinement_json_payload(value: object) -> object:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _refinement_json_payload(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_refinement_json_payload(item) for item in value]
    return value


def _write_refinement_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(
            _refinement_json_payload(value),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_refinement_jsonl(path: Path, values: tuple[object, ...]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for value in values:
            payload = _refinement_json_payload(value)
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
