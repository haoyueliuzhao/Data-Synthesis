from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
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
) -> V09RefinementManifest:
    resolved_cells = dict(task_cells or legacy_synthesis_cells(exposures))
    if set(item.task_id for item in exposures) - set(resolved_cells):
        raise ValueError("every feedback exposure requires a synthesis cell")
    unique_cells = {cell.cell_id: cell for cell in resolved_cells.values()}
    pattern_catalog_hash = canonical_hash(
        tuple(sorted({item.pattern_id for item in unique_cells.values()})),
        prefix="training_utility_v09_pattern_catalog:",
    )
    cohort_contracts = _cohort_contracts(config, pattern_catalog_hash)
    failures = aggregate_pattern_clause_failures(exposures, signals)
    capability_count = sum(item.route == FeedbackRoute.AGENT_CAPABILITY_GAP for item in signals)
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
        resolved_cells,
        target_probabilities=target_probabilities,
    )
    calibrated_feedback = calibrate_clause_feedback(
        signals,
        resolved_cells,
        calibration,
        uncalibrated_reliability=config.ccgr_uncalibrated_reliability,
    )
    raw_feedback = calibrate_clause_feedback(
        signals,
        resolved_cells,
        calibration,
        force_raw_reliability=True,
    )
    calibrated_statistics = aggregate_cell_feedback(
        prior_policy,
        exposures,
        calibrated_feedback,
        resolved_cells,
    )
    raw_statistics = aggregate_cell_feedback(
        prior_policy,
        exposures,
        raw_feedback,
        resolved_cells,
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
        "Selected=used=cited evidence remains a controlled-task assumption.",
        "External native benchmarks have not been executed.",
        *(
            ()
            if round0_real_agent_feedback
            else ("Offline typed counterfactual feedback is not a real-agent Round-0 result.",)
        ),
        *(
            ()
            if any(
                item.route == FeedbackRoute.UPSTREAM_DATA_DEFECT
                for item in calibrated_feedback
            )
            else (
                "This feedback slice contains no synthesis-defect root; beta is not "
                "empirically identified by this run.",
            )
        ),
        *(
            ()
            if calibration_coverage == 1.0
            else (
                "Uncalibrated observed root Clause kinds retain zero refinement weight.",
            )
        ),
    )
    route_counts = Counter(item.route.value for item in signals)
    identity = {
        "config_hash": config.config_hash,
        "feedback_source": feedback_source,
        "round0_real_agent_feedback": round0_real_agent_feedback,
        "exposures": exposures,
        "signals": signals,
        "allocations": allocations,
        "synthesis_cells": tuple(unique_cells.values()),
        "clause_feedback": calibrated_feedback,
        "ccgr_updates": ccgr_updates,
        "online_gate": gate,
        "cohorts": cohort_contracts,
    }
    return V09RefinementManifest(
        manifest_id=canonical_hash(identity, prefix="training_utility_v09_manifest:"),
        config_hash=config.config_hash,
        pattern_catalog_hash=pattern_catalog_hash,
        feedback_source=feedback_source,
        round0_real_agent_feedback=round0_real_agent_feedback,
        feedback_exposure_count=len(exposures),
        feedback_signal_count=len(signals),
        feedback_route_counts=dict(sorted(route_counts.items())),
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
    calibration, calibration_hash = clause_calibration_from_reports(calibration_reports)
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
    )


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
    counts = Counter(
        (task_domains[task_id], cell.cell_id)
        for task_id, cell in task_cells.items()
    )
    domain_totals = Counter(task_domains.values())
    targets: dict[str, float] = defaultdict(float)
    for (domain, cell_id), count in counts.items():
        targets[cell_id] += domain_weights.get(domain, 0.0) * count / domain_totals[domain]
    return dict(sorted(targets.items()))
