from __future__ import annotations

import argparse
import math
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any, Literal

from trusted_synthesis.core.vtdo import (
    ContributionEstimationManifest,
    ContributionProductionAuthorization,
    contribution_distribution_contract_hash,
    contribution_task_population_hash,
    make_contribution_production_authorization,
    make_contribution_rank_validation_evidence,
    make_probe_optimizer_contract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_contribution_horizon import (
    _pair_report,
    _state_values,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_contribution_intervention import (
    CONTRIBUTION_INTERVENTION_VERSION,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_contribution_population import (
    CENTERING_POLICY,
    CONTRIBUTION_POPULATION_VERSION,
    PRODUCTION_CONTRIBUTION_FIELD,
    PRODUCTION_MINIMUM_SEEDS_PER_SPLIT,
    STATE_PROBABILITY_POLICY,
    _current_distribution_hash,
    _current_state_probabilities,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_probe_gpu import (
    _read_json,
    _write_json,
)
from trusted_synthesis.hashing import canonical_hash

CONTRIBUTION_ESTIMAND_ANALYSIS_VERSION = "finance_contribution_estimand_analysis.v6"
CONTRIBUTION_TARGET_METRIC_ID = "negative_supervised_token_nll"
CORE_PRODUCTION_CONTRIBUTION_FIELD = "conservative_centered_contribution"
PRODUCTION_MINIMUM_TASK_COUNT = 30
PRODUCTION_MINIMUM_EVALUATION_RECORDS = 5


def _assert_canonical_artifact_hash(
    artifact: dict[str, Any],
    *,
    field: str,
    prefix: str,
    label: str,
) -> None:
    observed = artifact.get(field)
    if not observed:
        raise ValueError(f"{label} is missing {field}")
    payload = dict(artifact)
    payload.pop(field)
    expected = canonical_hash(payload, prefix=prefix)
    if observed != expected:
        raise ValueError(f"{label} {field} does not replay")


def _require_same(
    left: dict[str, Any],
    right: dict[str, Any],
    field: str,
    *,
    label: str,
) -> None:
    if field not in left or field not in right:
        raise ValueError(f"{label} is missing identity field:{field}")
    if left[field] != right[field]:
        raise ValueError(f"{label} identity mismatch:{field}")


def _require_report_plan_value(
    report: dict[str, Any],
    plan: dict[str, Any],
    report_field: str,
    *,
    plan_field: str | None = None,
    label: str,
) -> None:
    source_field = plan_field or report_field
    if report_field not in report or source_field not in plan:
        raise ValueError(f"{label} is missing identity field:{report_field}")
    if report[report_field] != plan[source_field]:
        raise ValueError(f"{label} identity mismatch:{report_field}")


def _replay_population_distribution_contract(
    plan: dict[str, Any],
    report: dict[str, Any],
) -> str:
    """Independently replay the pi_t support, weights and centered signals."""

    if plan.get("centering_policy") != CENTERING_POLICY:
        raise ValueError("Probe plan uses an unsupported centering policy")
    if plan.get("state_probability_policy") != STATE_PROBABILITY_POLICY:
        raise ValueError("Probe plan uses an unsupported state-probability policy")
    for field in ("centering_policy", "state_probability_policy"):
        _require_report_plan_value(
            report,
            plan,
            field,
            label="Probe distribution contract",
        )

    job_states: defaultdict[str, list[str]] = defaultdict(list)
    job_pairs: set[tuple[str, str]] = set()
    for job in plan["jobs"]:
        task_id = str(job["task_id"])
        state_id = str(job["state_id"])
        if not task_id or not state_id or (task_id, state_id) in job_pairs:
            raise ValueError("Probe plan has invalid task/state jobs")
        job_pairs.add((task_id, state_id))
        job_states[task_id].append(state_id)

    report_states: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in report["state_rows"]:
        report_states[str(row["task_id"])].append(row)
    if set(report_states) != set(job_states):
        raise ValueError("Probe report changed the task support of pi_t")

    task_audits = {str(row["task_id"]): row for row in report["task_rows"]}
    if len(task_audits) != len(report["task_rows"]) or set(task_audits) != set(job_states):
        raise ValueError("Probe task-level distribution audit is incomplete")

    task_distribution_hashes: dict[str, str] = {}
    for task_id in sorted(job_states):
        rows = report_states[task_id]
        row_by_state = {str(row["state_id"]): row for row in rows}
        if len(row_by_state) != len(rows) or set(row_by_state) != set(job_states[task_id]):
            raise ValueError("Probe report changed the state support of pi_t")
        probabilities = _current_state_probabilities(
            rows,
            policy=str(plan["state_probability_policy"]),
        )
        for state_id, probability in probabilities.items():
            if not math.isclose(
                float(row_by_state[state_id].get("current_probability", -1.0)),
                probability,
                abs_tol=1e-12,
            ):
                raise ValueError("Probe report changed a current state probability")

        audit = task_audits[task_id]
        expected_hash = _current_distribution_hash(task_id, probabilities)
        if audit.get("current_distribution_hash") != expected_hash:
            raise ValueError("Probe task distribution hash does not replay")
        task_distribution_hashes[task_id] = expected_hash
        for audit_field, value_suffix in (
            ("weighted_centered_means", "centered_contribution"),
            (
                "weighted_conservative_centered_means",
                "conservative_centered_contribution",
            ),
        ):
            observed = audit.get(audit_field)
            if not isinstance(observed, dict) or set(observed) != {
                "estimation",
                "validation",
                "all_seed",
            }:
                raise ValueError("Probe weighted-centering audit is incomplete")
            for split in ("estimation", "validation", "all_seed"):
                expected_mean = sum(
                    probabilities[state_id]
                    * float(row_by_state[state_id][f"{split}_{value_suffix}"])
                    for state_id in probabilities
                )
                if not math.isclose(expected_mean, 0.0, abs_tol=1e-12):
                    raise ValueError("Probe signal is not centered under current pi_t")
                if not math.isclose(
                    float(observed[split]),
                    expected_mean,
                    abs_tol=1e-12,
                ):
                    raise ValueError("Probe weighted-centering audit does not replay")

    if report.get("task_distribution_hashes") != task_distribution_hashes:
        raise ValueError("Probe report task-distribution hashes do not replay")
    expected_contract_hash = contribution_distribution_contract_hash(task_distribution_hashes)
    if report.get("current_distribution_contract_hash") != expected_contract_hash:
        raise ValueError("Probe current-distribution contract hash does not replay")
    if report.get("weighted_centering_replay_passed") is not True:
        raise ValueError("Probe report did not pass weighted-centering replay")
    return expected_contract_hash


def _strict_rebind_contract(
    population_plan: dict[str, Any],
    population_report: dict[str, Any],
    intervention_plan: dict[str, Any],
    intervention_report: dict[str, Any],
) -> dict[str, Any]:
    """Prove that an independent Intervention can evaluate a newer Probe signal.

    An Intervention may have been frozen against an earlier Probe report. Reuse is
    permitted only when every model, data, task-state, optimizer, horizon and
    evaluation identity is equal. The original report lineage remains immutable.
    """

    _assert_canonical_artifact_hash(
        population_plan,
        field="plan_hash",
        prefix="finance_contribution_population_plan:",
        label="Probe plan",
    )
    _assert_canonical_artifact_hash(
        population_report,
        field="report_hash",
        prefix="finance_contribution_population_report:",
        label="Probe report",
    )
    _assert_canonical_artifact_hash(
        intervention_plan,
        field="plan_hash",
        prefix="finance_contribution_intervention_plan:",
        label="Intervention plan",
    )
    _assert_canonical_artifact_hash(
        intervention_report,
        field="report_hash",
        prefix="finance_contribution_intervention_report:",
        label="Intervention report",
    )
    if population_plan.get("experiment_version") != CONTRIBUTION_POPULATION_VERSION:
        raise ValueError("Contribution analysis requires the current Probe contract")
    if population_report.get("experiment_version") != CONTRIBUTION_POPULATION_VERSION:
        raise ValueError("Contribution analysis requires the current Probe report")
    if intervention_plan.get("experiment_version") != CONTRIBUTION_INTERVENTION_VERSION:
        raise ValueError("Contribution analysis requires the current Intervention contract")
    if intervention_report.get("experiment_version") != CONTRIBUTION_INTERVENTION_VERSION:
        raise ValueError("Contribution analysis requires the current Intervention report")
    if population_report.get("plan_hash") != population_plan["plan_hash"]:
        raise ValueError("Probe report does not replay its plan")
    if intervention_report.get("plan_hash") != intervention_plan["plan_hash"]:
        raise ValueError("Intervention report does not replay its plan")
    current_distribution_contract_hash = _replay_population_distribution_contract(
        population_plan, population_report
    )
    if intervention_report.get("source_population_report_hash") != intervention_plan.get(
        "source_population_report_hash"
    ):
        raise ValueError("Intervention report changed its frozen Probe lineage")
    for field in (
        "probe_step_count",
        "learning_rate",
        "probe_optimizer",
        "task_count",
        "final_test_set_id",
        "internal_validation_set_id",
        "uncertainty_penalty_coefficient",
        "estimation_seeds",
        "validation_seeds",
    ):
        _require_report_plan_value(
            population_report,
            population_plan,
            field,
            label="Probe report/plan",
        )
    for field in (
        "intervention_step_count",
        "learning_rate",
        "intervention_optimizer",
        "optimizer_alignment_role",
        "final_test_set_id",
        "probe_contribution_signal_kind",
        "probe_uncertainty_penalty_coefficient",
    ):
        _require_report_plan_value(
            intervention_report,
            intervention_plan,
            field,
            label="Intervention report/plan",
        )
    if int(population_report.get("seed_count", -1)) != len(population_plan["probe_seeds"]):
        raise ValueError("Probe report seed count does not replay its plan")
    if int(intervention_report.get("intervention_seed_count", -1)) != len(
        intervention_plan["intervention_seeds"]
    ):
        raise ValueError("Intervention report seed count does not replay its plan")
    for label, plan, report, seed_field in (
        ("Probe", population_plan, population_report, "probe_seeds"),
        ("Intervention", intervention_plan, intervention_report, "intervention_seeds"),
    ):
        expected_states = len(plan["jobs"])
        if int(report.get("state_count", -1)) != expected_states:
            raise ValueError(f"{label} report state count does not replay its jobs")
        expected_observations = expected_states * len(plan[seed_field])
        if int(report.get("observation_count", -1)) != expected_observations:
            raise ValueError(f"{label} report observation count does not replay its jobs")

    for field in (
        "base_model_manifest_hash",
        "beneficiary_adapter_tensor_sha256",
        "beneficiary_model_state_id",
        "beneficiary_checkpoint_hash",
        "source_records_sha256",
        "target_records_sha256",
        "task_count",
        "learning_rate",
        "jobs",
    ):
        _require_same(population_plan, intervention_plan, field, label="Probe/Intervention")
    if tuple(population_plan["final_test_record_ids"]) != tuple(
        intervention_plan["final_test_record_ids"]
    ):
        raise ValueError("Probe/Intervention identity mismatch:final_test_record_ids")
    if int(population_plan["probe_step_count"]) != int(
        intervention_plan["intervention_step_count"]
    ):
        raise ValueError("Probe/Intervention identity mismatch:adaptation_horizon")
    if population_plan.get("probe_optimizer") != "cold_start_sgd":
        raise ValueError("Probe analysis requires cold-start SGD")
    if intervention_plan.get("intervention_optimizer") != "cold_start_sgd":
        raise ValueError("Independent validity requires same-optimizer cold-start SGD")
    if intervention_plan.get("optimizer_alignment_role") != "same_optimizer_estimand":
        raise ValueError("Intervention is not a same-optimizer estimand")
    expected_optimizer = {
        "optimizer": "cold_start_sgd",
        "learning_rate": population_plan["learning_rate"],
        "step_count": population_plan["probe_step_count"],
        "momentum": 0.0,
        "weight_decay": 0.0,
        "gradient_clipping": False,
        "gradient_clip_norm": None,
        "optimizer_state_policy": "empty_at_each_task_state",
    }
    if intervention_plan.get("optimizer_contract") != expected_optimizer:
        raise ValueError("Intervention optimizer contract is not Probe-equivalent")
    adaptation_horizon = int(population_plan["probe_step_count"])
    optimizer_contract_id = (
        make_probe_optimizer_contract(
            learning_rate=float(population_plan["learning_rate"]),
            step_count=adaptation_horizon,
        ).contract_id
        if adaptation_horizon <= 3
        else None
    )
    expected_probe_estimand_id = canonical_hash(
        {
            "beneficiary_checkpoint_hash": population_plan["beneficiary_checkpoint_hash"],
            "internal_validation_set_id": _internal_validation_set_id(population_plan),
            "source_records_sha256": population_plan["source_records_sha256"],
            "metric": CONTRIBUTION_TARGET_METRIC_ID,
            "evaluation_role": "internal_validation",
            "probe_step_count": population_plan["probe_step_count"],
            "learning_rate": population_plan["learning_rate"],
            "optimizer": "cold_start_sgd",
            "uncertainty_statistic": population_plan["uncertainty_statistic"],
            "uncertainty_penalty_coefficient": population_plan["uncertainty_penalty_coefficient"],
            "centering_policy": population_plan["centering_policy"],
        },
        prefix="finance_contribution_probe_estimand:",
    )
    if population_plan.get("probe_estimand_id") != expected_probe_estimand_id:
        raise ValueError("Probe estimand identity does not replay")
    if intervention_plan.get("metric") != CONTRIBUTION_TARGET_METRIC_ID:
        raise ValueError("Intervention uses another target metric")
    expected_intervention_estimand_id = canonical_hash(
        {
            "beneficiary_checkpoint_hash": intervention_plan["beneficiary_checkpoint_hash"],
            "final_test_set_id": intervention_plan["final_test_set_id"],
            "target_records_sha256": intervention_plan["target_records_sha256"],
            "metric": intervention_plan["metric"],
            "evaluation_role": intervention_plan["evaluation_role"],
            "intervention_step_count": intervention_plan["intervention_step_count"],
            "learning_rate": intervention_plan["learning_rate"],
            "optimizer_contract": intervention_plan["optimizer_contract"],
            "optimizer_alignment_role": intervention_plan["optimizer_alignment_role"],
        },
        prefix="finance_contribution_intervention_estimand:",
    )
    if intervention_plan.get("intervention_estimand_id") != expected_intervention_estimand_id:
        raise ValueError("Intervention estimand identity does not replay")
    if set(population_plan["probe_seeds"]) & set(intervention_plan["intervention_seeds"]):
        raise ValueError("Probe and Intervention seeds must be disjoint")
    if population_report.get("production_contribution_field") != PRODUCTION_CONTRIBUTION_FIELD:
        raise ValueError("Probe report does not freeze the production Contribution field")
    if intervention_plan.get("probe_contribution_signal_kind") != PRODUCTION_CONTRIBUTION_FIELD:
        raise ValueError("Intervention lineage used another production Contribution field")
    if intervention_plan.get("probe_uncertainty_penalty_coefficient") != population_report.get(
        "uncertainty_penalty_coefficient"
    ):
        raise ValueError("Probe/Intervention uncertainty penalty mismatch")
    if population_report.get("final_test_set_id") != population_plan.get("final_test_set_id"):
        raise ValueError("Probe report changed its final-test identity")
    if intervention_report.get("final_test_set_id") != intervention_plan.get("final_test_set_id"):
        raise ValueError("Intervention report changed its final-test identity")

    final_test_content_hash = canonical_hash(
        tuple(population_plan["final_test_record_ids"]),
        prefix="finance_contribution_final_test_records:",
    )
    direct_lineage = (
        intervention_plan["source_population_report_hash"] == population_report["report_hash"]
    )
    return {
        "mode": "direct_lineage" if direct_lineage else "strict_identity_reanalysis",
        "identity_validated": True,
        "source_population_report_hash": intervention_plan["source_population_report_hash"],
        "evaluated_population_report_hash": population_report["report_hash"],
        "beneficiary_model_state_id": population_plan["beneficiary_model_state_id"],
        "beneficiary_checkpoint_hash": population_plan["beneficiary_checkpoint_hash"],
        "target_metric_id": CONTRIBUTION_TARGET_METRIC_ID,
        "state_probability_policy": population_plan["state_probability_policy"],
        "current_distribution_contract_hash": current_distribution_contract_hash,
        "task_distribution_hashes": dict(population_report["task_distribution_hashes"]),
        "probe_optimizer_contract_id": optimizer_contract_id,
        "adaptation_horizon": adaptation_horizon,
        "uncertainty_statistic": population_plan["uncertainty_statistic"],
        "uncertainty_penalty_coefficient": population_plan["uncertainty_penalty_coefficient"],
        "internal_validation_set_id": _internal_validation_set_id(population_plan),
        "probe_final_test_set_id": population_plan["final_test_set_id"],
        "independent_final_test_set_id": intervention_plan["final_test_set_id"],
        "target_records_sha256": population_plan["target_records_sha256"],
        "task_state_jobs_hash": canonical_hash(
            population_plan["jobs"],
            prefix="finance_contribution_task_state_jobs:",
        ),
        "final_test_records_hash": final_test_content_hash,
        "seed_disjoint": True,
        "same_optimizer_estimand": True,
    }


def _passes_rank_gate(comparison: dict[str, Any]) -> bool:
    return bool(
        comparison["macro_task_spearman_ci95"][0] > 0
        and comparison["macro_pairwise_concordance_ci95"][0] > 0.5
        and comparison["winner_agreement_rate"] >= 0.5
        and comparison["permutation_test"]["macro_spearman_p_value"] < 0.05
        and comparison["permutation_test"]["macro_pairwise_concordance_p_value"] < 0.05
    )


def _internal_validation_set_id(plan: dict[str, Any]) -> str:
    value = plan.get("internal_validation_set_id")
    if value:
        return str(value)
    return canonical_hash(
        tuple(plan["validation_record_ids"]),
        prefix="finance_contribution_internal_validation:",
    )


def _rank_validation_evidence(
    comparison: dict[str, Any],
    *,
    role: Literal[
        "cross_seed_stability",
        "independent_final_test",
        "heldout_final_test",
    ],
):
    permutation = comparison["permutation_test"]
    return make_contribution_rank_validation_evidence(
        evaluation_role=role,
        macro_task_spearman=float(comparison["macro_task_spearman"]),
        macro_task_spearman_ci95=tuple(comparison["macro_task_spearman_ci95"]),
        macro_pairwise_concordance=float(comparison["macro_pairwise_concordance"]),
        macro_pairwise_concordance_ci95=tuple(comparison["macro_pairwise_concordance_ci95"]),
        winner_agreement_rate=float(comparison["winner_agreement_rate"]),
        macro_spearman_p_value=float(permutation["macro_spearman_p_value"]),
        macro_pairwise_concordance_p_value=float(permutation["macro_pairwise_concordance_p_value"]),
    )


def issue_contribution_production_authorization(
    *,
    analysis_report: dict[str, Any],
    manifest: ContributionEstimationManifest,
) -> ContributionProductionAuthorization:
    """Issue the only credential that lets a real Probe affect VTDO energy."""

    _assert_canonical_artifact_hash(
        analysis_report,
        field="report_hash",
        prefix="finance_contribution_estimand_analysis:",
        label="Contribution estimand analysis",
    )
    if analysis_report.get("analysis_version") != CONTRIBUTION_ESTIMAND_ANALYSIS_VERSION:
        raise ValueError("Contribution authorization requires the current analysis contract")
    if not (
        analysis_report.get("production_contribution_allowed") is True
        and analysis_report.get("production_authorization_issuable") is True
        and analysis_report.get("status") == "passed"
        and all(analysis_report.get("production_support_gates", {}).values())
    ):
        raise ValueError("Contribution analysis did not pass all production gates")
    if int(analysis_report.get("minimum_task_count", 0)) < PRODUCTION_MINIMUM_TASK_COUNT:
        raise ValueError("Contribution analysis weakened the task-population gate")
    if (
        int(analysis_report.get("minimum_evaluation_records", 0))
        < PRODUCTION_MINIMUM_EVALUATION_RECORDS
    ):
        raise ValueError("Contribution analysis weakened the evaluation-support gate")
    if (
        int(analysis_report.get("minimum_seed_replicates_per_role", 0))
        < PRODUCTION_MINIMUM_SEEDS_PER_SPLIT
    ):
        raise ValueError("Contribution analysis weakened the seed-replication gate")
    selected_seed_counts = analysis_report.get("selected_seed_counts")
    if (
        not isinstance(selected_seed_counts, dict)
        or min(int(value) for value in selected_seed_counts.values())
        < PRODUCTION_MINIMUM_SEEDS_PER_SPLIT
    ):
        raise ValueError("Contribution authorization lacks four seeds per role")
    horizon = analysis_report.get("validated_production_horizon")
    if horizon is None:
        raise ValueError("Contribution analysis did not validate a production horizon")
    selected_rows = [
        item for item in analysis_report["horizon_rows"] if int(item["horizon"]) == int(horizon)
    ]
    if len(selected_rows) != 1 or selected_rows[0].get("rank_gate_passed") is not True:
        raise ValueError("validated Contribution horizon has no unique passing evidence")
    selected = selected_rows[0]
    rebind = selected["rebind_contract"]
    expected_manifest_identity = {
        "beneficiary_model_state_id": rebind["beneficiary_model_state_id"],
        "beneficiary_checkpoint_hash": rebind["beneficiary_checkpoint_hash"],
        "target_metric_id": rebind["target_metric_id"],
        "probe_optimizer_contract_id": rebind["probe_optimizer_contract_id"],
        "probe_adaptation_horizon": int(horizon),
        "uncertainty_statistic": rebind["uncertainty_statistic"],
        "uncertainty_penalty_coefficient": rebind["uncertainty_penalty_coefficient"],
        "production_contribution_field": CORE_PRODUCTION_CONTRIBUTION_FIELD,
        "target_evaluation_distribution_id": analysis_report["internal_validation_set_id"],
        "final_test_set_id": analysis_report["final_test_set_id"],
    }
    observed_manifest_identity = manifest.model_dump(
        mode="python", include=set(expected_manifest_identity)
    )
    if observed_manifest_identity != expected_manifest_identity:
        mismatched = tuple(
            key
            for key, value in expected_manifest_identity.items()
            if observed_manifest_identity.get(key) != value
        )
        raise ValueError(f"Contribution manifest does not match validated analysis:{mismatched}")
    seed_counts = analysis_report["selected_seed_counts"]
    return make_contribution_production_authorization(
        manifest=manifest,
        analysis_version=str(analysis_report["analysis_version"]),
        analysis_report_hash=str(analysis_report["report_hash"]),
        task_condition_ids=analysis_report["task_condition_ids"],
        task_distribution_hashes=analysis_report["task_distribution_hashes"],
        task_count=int(analysis_report["task_count"]),
        state_count=int(analysis_report["state_count"]),
        internal_validation_record_count=int(analysis_report["internal_validation_record_count"]),
        final_test_record_count=int(analysis_report["final_test_record_count"]),
        estimation_seed_count=int(seed_counts["estimation"]),
        validation_seed_count=int(seed_counts["validation"]),
        intervention_seed_count=int(seed_counts["intervention"]),
        cross_seed_stability=_rank_validation_evidence(
            selected["seed_stability"], role="cross_seed_stability"
        ),
        independent_final_test=_rank_validation_evidence(
            selected["independent_final_test_validity"],
            role="independent_final_test",
        ),
        heldout_final_test=_rank_validation_evidence(
            selected["heldout_final_test_validity"],
            role="heldout_final_test",
        ),
    )


def analyze_contribution_estimands(
    *,
    population_runs: list[tuple[dict[str, Any], dict[str, Any]]],
    intervention_runs: list[tuple[dict[str, Any], dict[str, Any]]],
    bootstrap_samples: int = 2000,
    permutation_iterations: int = 10000,
    minimum_task_count: int = 30,
    minimum_evaluation_records: int = 5,
    minimum_seed_replicates_per_role: int = 4,
) -> dict[str, Any]:
    if minimum_task_count < PRODUCTION_MINIMUM_TASK_COUNT:
        raise ValueError("production task threshold cannot be lower than 30")
    if minimum_evaluation_records < PRODUCTION_MINIMUM_EVALUATION_RECORDS:
        raise ValueError("production evaluation threshold cannot be lower than 5")
    if minimum_seed_replicates_per_role < PRODUCTION_MINIMUM_SEEDS_PER_SPLIT:
        raise ValueError("production seed threshold cannot be lower than 4 per role")
    if not population_runs or not intervention_runs:
        raise ValueError("Contribution estimand analysis requires Probe and Intervention runs")
    populations: dict[int, tuple[dict[str, Any], dict[str, Any]]] = {}
    for plan, report in population_runs:
        horizon = int(plan["probe_step_count"])
        if horizon in populations:
            raise ValueError(f"duplicate Probe horizon:{horizon}")
        populations[horizon] = (plan, report)
    interventions: dict[int, tuple[dict[str, Any], dict[str, Any]]] = {}
    for plan, report in intervention_runs:
        horizon = int(plan["intervention_step_count"])
        if horizon in interventions:
            raise ValueError(f"duplicate Intervention horizon:{horizon}")
        interventions[horizon] = (plan, report)
    if set(populations) != set(interventions):
        raise ValueError("Probe and Intervention horizons must match exactly")
    rebind_contracts = {
        horizon: _strict_rebind_contract(
            populations[horizon][0],
            populations[horizon][1],
            interventions[horizon][0],
            interventions[horizon][1],
        )
        for horizon in sorted(populations)
    }

    current_distribution_contract_hashes = {
        str(contract["current_distribution_contract_hash"])
        for contract in rebind_contracts.values()
    }
    if len(current_distribution_contract_hashes) != 1:
        raise ValueError("Probe horizons use different current pi_t distributions")
    task_distribution_hashes = dict(
        next(iter(rebind_contracts.values()))["task_distribution_hashes"]
    )
    if any(
        dict(contract["task_distribution_hashes"]) != task_distribution_hashes
        for contract in rebind_contracts.values()
    ):
        raise ValueError("Probe horizons use different task-level pi_t mappings")
    internal_set_ids = {_internal_validation_set_id(plan) for plan, _ in populations.values()}
    probe_final_set_ids = {str(plan["final_test_set_id"]) for plan, _ in populations.values()}
    independent_final_set_ids = {
        str(plan["final_test_set_id"]) for plan, _ in interventions.values()
    }
    if len(internal_set_ids) != 1:
        raise ValueError("Probe horizons use different internal-validation sets")
    if len(probe_final_set_ids) != 1 or len(independent_final_set_ids) != 1:
        raise ValueError("Contribution horizons use different final-test sets")
    population_final_records = {
        tuple(plan["final_test_record_ids"]) for plan, _ in populations.values()
    }
    intervention_final_records = {
        tuple(plan["final_test_record_ids"]) for plan, _ in interventions.values()
    }
    if len(population_final_records) != 1 or population_final_records != intervention_final_records:
        raise ValueError("Probe and Intervention do not use the same final-test records")

    estimands: dict[str, dict[tuple[str, str], float]] = {}
    population_metadata: list[dict[str, Any]] = []
    intervention_metadata: list[dict[str, Any]] = []
    for horizon, (plan, report) in sorted(populations.items()):
        estimation_id = f"probe_estimation_h{horizon}_internal_validation"
        validation_id = f"probe_validation_h{horizon}_internal_validation"
        estimands[estimation_id] = _state_values(
            report["state_rows"],
            value_field="estimation_conservative_centered_contribution",
        )
        estimands[validation_id] = _state_values(
            report["state_rows"],
            value_field="validation_conservative_centered_contribution",
        )
        estimands[f"probe_estimation_raw_h{horizon}_internal_validation"] = _state_values(
            report["state_rows"],
            value_field="estimation_centered_contribution",
        )
        estimands[f"probe_validation_raw_h{horizon}_internal_validation"] = _state_values(
            report["state_rows"],
            value_field="validation_centered_contribution",
        )
        population_metadata.append(
            {
                "horizon": horizon,
                "estimation_estimand_id": estimation_id,
                "validation_estimand_id": validation_id,
                "probe_estimand_id": plan.get("probe_estimand_id"),
                "plan_hash": plan["plan_hash"],
                "report_hash": report["report_hash"],
                "state_probability_policy": report["state_probability_policy"],
                "current_distribution_contract_hash": report["current_distribution_contract_hash"],
                "estimation_seeds": plan["estimation_seeds"],
                "validation_seeds": plan["validation_seeds"],
                "production_contribution_field": report["production_contribution_field"],
                "uncertainty_penalty_coefficient": report["uncertainty_penalty_coefficient"],
            }
        )
    for horizon, (plan, report) in sorted(interventions.items()):
        estimand_id = f"intervention_h{horizon}_final_test"
        estimands[estimand_id] = _state_values(
            report["state_rows"],
            value_field="intervention_mean_gain",
        )
        intervention_metadata.append(
            {
                "horizon": horizon,
                "estimand_id": estimand_id,
                "intervention_estimand_id": plan.get("intervention_estimand_id"),
                "plan_hash": plan["plan_hash"],
                "report_hash": report["report_hash"],
                "intervention_seeds": plan["intervention_seeds"],
                "rebind_contract": rebind_contracts[horizon],
            }
        )
    support = set(next(iter(estimands.values())))
    if any(set(values) != support for values in estimands.values()):
        raise ValueError("Contribution estimands do not share exact task/state support")

    horizon_rows: list[dict[str, Any]] = []
    comparison_seed = 20261000
    for horizon in sorted(populations):
        estimation_id = f"probe_estimation_h{horizon}_internal_validation"
        validation_id = f"probe_validation_h{horizon}_internal_validation"
        intervention_id = f"intervention_h{horizon}_final_test"
        raw_estimation_id = f"probe_estimation_raw_h{horizon}_internal_validation"
        raw_validation_id = f"probe_validation_raw_h{horizon}_internal_validation"
        seed_stability = _pair_report(
            estimation_id,
            validation_id,
            estimands[estimation_id],
            estimands[validation_id],
            bootstrap_samples=bootstrap_samples,
            permutation_iterations=permutation_iterations,
            seed=comparison_seed,
        )
        comparison_seed += 10
        raw_seed_stability = _pair_report(
            raw_estimation_id,
            raw_validation_id,
            estimands[raw_estimation_id],
            estimands[raw_validation_id],
            bootstrap_samples=bootstrap_samples,
            permutation_iterations=permutation_iterations,
            seed=comparison_seed,
        )
        comparison_seed += 10
        independent_validity = _pair_report(
            estimation_id,
            intervention_id,
            estimands[estimation_id],
            estimands[intervention_id],
            bootstrap_samples=bootstrap_samples,
            permutation_iterations=permutation_iterations,
            seed=comparison_seed,
        )
        comparison_seed += 10
        raw_independent_validity = _pair_report(
            raw_estimation_id,
            intervention_id,
            estimands[raw_estimation_id],
            estimands[intervention_id],
            bootstrap_samples=bootstrap_samples,
            permutation_iterations=permutation_iterations,
            seed=comparison_seed,
        )
        comparison_seed += 10
        heldout_validity = _pair_report(
            validation_id,
            intervention_id,
            estimands[validation_id],
            estimands[intervention_id],
            bootstrap_samples=bootstrap_samples,
            permutation_iterations=permutation_iterations,
            seed=comparison_seed,
        )
        comparison_seed += 10
        raw_heldout_validity = _pair_report(
            raw_validation_id,
            intervention_id,
            estimands[raw_validation_id],
            estimands[intervention_id],
            bootstrap_samples=bootstrap_samples,
            permutation_iterations=permutation_iterations,
            seed=comparison_seed,
        )
        comparison_seed += 10
        conservative_lift = {
            "estimation_to_final_test_spearman": (
                independent_validity["macro_task_spearman"]
                - raw_independent_validity["macro_task_spearman"]
            ),
            "estimation_to_final_test_pairwise_concordance": (
                independent_validity["macro_pairwise_concordance"]
                - raw_independent_validity["macro_pairwise_concordance"]
            ),
            "estimation_to_final_test_winner_agreement": (
                independent_validity["winner_agreement_rate"]
                - raw_independent_validity["winner_agreement_rate"]
            ),
            "heldout_to_final_test_spearman": (
                heldout_validity["macro_task_spearman"]
                - raw_heldout_validity["macro_task_spearman"]
            ),
            "heldout_to_final_test_pairwise_concordance": (
                heldout_validity["macro_pairwise_concordance"]
                - raw_heldout_validity["macro_pairwise_concordance"]
            ),
        }
        rank_gate_components = {
            "cross_seed_stability": _passes_rank_gate(seed_stability),
            "estimation_to_final_test": _passes_rank_gate(independent_validity),
            "heldout_to_final_test": _passes_rank_gate(heldout_validity),
        }
        eligible = all(rank_gate_components.values())
        point_robustness_score = min(
            float(seed_stability["macro_task_spearman"]),
            float(seed_stability["macro_pairwise_concordance"]),
            float(independent_validity["macro_task_spearman"]),
            float(independent_validity["macro_pairwise_concordance"]),
            float(heldout_validity["macro_task_spearman"]),
            float(heldout_validity["macro_pairwise_concordance"]),
        )
        confidence_margin_score = min(
            float(seed_stability["macro_task_spearman_ci95"][0]),
            float(seed_stability["macro_pairwise_concordance_ci95"][0]) - 0.5,
            float(independent_validity["macro_task_spearman_ci95"][0]),
            float(independent_validity["macro_pairwise_concordance_ci95"][0]) - 0.5,
            float(heldout_validity["macro_task_spearman_ci95"][0]),
            float(heldout_validity["macro_pairwise_concordance_ci95"][0]) - 0.5,
        )
        horizon_rows.append(
            {
                "horizon": horizon,
                "rebind_contract": rebind_contracts[horizon],
                "seed_stability": seed_stability,
                "raw_seed_stability": raw_seed_stability,
                "independent_final_test_validity": independent_validity,
                "raw_independent_final_test_validity": raw_independent_validity,
                "heldout_final_test_validity": heldout_validity,
                "raw_heldout_final_test_validity": raw_heldout_validity,
                "conservative_signal_lift": conservative_lift,
                "rank_gate_components": rank_gate_components,
                "rank_gate_passed": eligible,
                "confidence_margin_score": confidence_margin_score,
                "point_robustness_score": point_robustness_score,
            }
        )

    cross_horizon_probe: list[dict[str, Any]] = []
    cross_horizon_intervention: list[dict[str, Any]] = []
    for left, right in combinations(sorted(populations), 2):
        left_probe = f"probe_estimation_h{left}_internal_validation"
        right_probe = f"probe_estimation_h{right}_internal_validation"
        cross_horizon_probe.append(
            _pair_report(
                left_probe,
                right_probe,
                estimands[left_probe],
                estimands[right_probe],
                bootstrap_samples=bootstrap_samples,
                permutation_iterations=permutation_iterations,
                seed=comparison_seed,
            )
        )
        comparison_seed += 10
        left_intervention = f"intervention_h{left}_final_test"
        right_intervention = f"intervention_h{right}_final_test"
        cross_horizon_intervention.append(
            _pair_report(
                left_intervention,
                right_intervention,
                estimands[left_intervention],
                estimands[right_intervention],
                bootstrap_samples=bootstrap_samples,
                permutation_iterations=permutation_iterations,
                seed=comparison_seed,
            )
        )
        comparison_seed += 10

    eligible_rows = [item for item in horizon_rows if item["rank_gate_passed"]]

    def select_horizon(
        rows: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        return (
            max(
                rows,
                key=lambda item: (
                    float(item["confidence_margin_score"]),
                    float(item["point_robustness_score"]),
                    -int(item["horizon"]),
                ),
            )
            if rows
            else None
        )

    exploratory_selected = select_horizon(eligible_rows)
    horizon_seed_counts = {
        str(horizon): {
            "estimation": len(populations[horizon][0]["estimation_seeds"]),
            "validation": len(populations[horizon][0]["validation_seeds"]),
            "intervention": len(interventions[horizon][0]["intervention_seeds"]),
        }
        for horizon in sorted(populations)
    }
    rank_validated_production_rows = [item for item in eligible_rows if int(item["horizon"]) <= 3]
    seed_replicated_production_rows = [
        item
        for item in horizon_rows
        if int(item["horizon"]) <= 3
        and min(horizon_seed_counts[str(item["horizon"])].values())
        >= minimum_seed_replicates_per_role
    ]
    seed_replicated_horizons = {int(item["horizon"]) for item in seed_replicated_production_rows}
    production_candidate_rows = [
        item
        for item in rank_validated_production_rows
        if int(item["horizon"]) in seed_replicated_horizons
    ]
    production_selected = select_horizon(production_candidate_rows)
    task_condition_ids = tuple(sorted({task_id for task_id, _ in support}))
    task_count = len(task_condition_ids)
    first_population_plan = next(iter(populations.values()))[0]
    first_intervention_plan = next(iter(interventions.values()))[0]
    internal_validation_count = len(first_population_plan["validation_record_ids"])
    final_test_count = len(first_intervention_plan["final_test_record_ids"])
    selected_seed_counts = (
        {
            "estimation": len(
                populations[int(production_selected["horizon"])][0]["estimation_seeds"]
            ),
            "validation": len(
                populations[int(production_selected["horizon"])][0]["validation_seeds"]
            ),
            "intervention": len(
                interventions[int(production_selected["horizon"])][0]["intervention_seeds"]
            ),
        }
        if production_selected
        else None
    )
    support_gates = {
        "validated_horizon_exists": bool(rank_validated_production_rows),
        "seed_replicates_sufficient": bool(seed_replicated_production_rows),
        "joint_horizon_eligibility": production_selected is not None,
        "task_population_sufficient": task_count >= minimum_task_count,
        "internal_validation_support_sufficient": (
            internal_validation_count >= minimum_evaluation_records
        ),
        "final_test_support_sufficient": final_test_count >= minimum_evaluation_records,
    }
    production_allowed = bool(all(support_gates.values()))
    production_blockers = tuple(key for key, passed in support_gates.items() if not passed)
    task_population_hash = contribution_task_population_hash(task_condition_ids)
    analysis_report: dict[str, Any] = {
        "analysis_version": CONTRIBUTION_ESTIMAND_ANALYSIS_VERSION,
        "horizons": sorted(populations),
        "state_probability_policy": STATE_PROBABILITY_POLICY,
        "current_distribution_contract_hash": next(iter(current_distribution_contract_hashes)),
        "task_distribution_hashes": task_distribution_hashes,
        "task_count": task_count,
        "state_count": len(support),
        "internal_validation_set_id": next(iter(internal_set_ids)),
        "internal_validation_record_count": internal_validation_count,
        "final_test_set_id": next(iter(probe_final_set_ids)),
        "independent_final_test_set_id": next(iter(independent_final_set_ids)),
        "final_test_record_count": final_test_count,
        "population_runs": population_metadata,
        "intervention_runs": intervention_metadata,
        "strict_rebind_contracts": [
            rebind_contracts[horizon] for horizon in sorted(rebind_contracts)
        ],
        "horizon_rows": horizon_rows,
        "cross_horizon_probe": cross_horizon_probe,
        "rank_validated_production_horizons": [
            int(item["horizon"]) for item in rank_validated_production_rows
        ],
        "production_seed_eligible_horizons": [
            int(item["horizon"]) for item in seed_replicated_production_rows
        ],
        "jointly_eligible_production_horizons": [
            int(item["horizon"]) for item in production_candidate_rows
        ],
        "cross_horizon_intervention": cross_horizon_intervention,
        "exploratory_selected_horizon": (
            int(exploratory_selected["horizon"]) if exploratory_selected else None
        ),
        "exploratory_confidence_margin_score": (
            float(exploratory_selected["confidence_margin_score"]) if exploratory_selected else None
        ),
        "exploratory_point_robustness_score": (
            float(exploratory_selected["point_robustness_score"]) if exploratory_selected else None
        ),
        "validated_production_horizon": (
            int(production_selected["horizon"])
            if production_allowed and production_selected
            else None
        ),
        "selected_seed_counts": selected_seed_counts,
        "horizon_seed_counts": horizon_seed_counts,
        "task_condition_ids": task_condition_ids,
        "task_population_hash": task_population_hash,
        "minimum_task_count": minimum_task_count,
        "minimum_evaluation_records": minimum_evaluation_records,
        "minimum_seed_replicates_per_role": minimum_seed_replicates_per_role,
        "production_support_gates": support_gates,
        "production_blockers": production_blockers,
        "production_contribution_allowed": production_allowed,
        "production_authorization_issuable": production_allowed,
        "recommended_production_action": (
            "enable_validated_horizon" if production_allowed else "disable_contribution_component"
        ),
        "status": "passed" if production_allowed else "partial",
        "claim_boundary": (
            "The selected horizon is exploratory until both the task-population and "
            "evaluation-support gates pass. C^h is not evidence for any other horizon "
            "or for full Student-training utility. Strict identity reanalysis preserves "
            "the original Intervention lineage and does not relabel old observations."
        ),
    }
    analysis_report["report_hash"] = canonical_hash(
        analysis_report,
        prefix="finance_contribution_estimand_analysis:",
    )
    return analysis_report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Select a horizon-specific VTDO Contribution estimand"
    )
    parser.add_argument("--population-dirs", required=True, nargs="+")
    parser.add_argument("--intervention-dirs", required=True, nargs="+")
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--bootstrap-samples", type=int, default=2000)
    parser.add_argument("--permutation-iterations", type=int, default=10000)
    parser.add_argument("--minimum-task-count", type=int, default=PRODUCTION_MINIMUM_TASK_COUNT)
    parser.add_argument(
        "--minimum-evaluation-records",
        type=int,
        default=PRODUCTION_MINIMUM_EVALUATION_RECORDS,
    )
    parser.add_argument(
        "--minimum-seed-replicates-per-role",
        type=int,
        default=PRODUCTION_MINIMUM_SEEDS_PER_SPLIT,
    )
    parser.add_argument("--contribution-manifest-path")
    parser.add_argument("--authorization-output-path")
    args = parser.parse_args()
    population_runs = []
    for raw_path in args.population_dirs:
        path = Path(raw_path).resolve()
        population_runs.append((_read_json(path / "plan.json"), _read_json(path / "report.json")))
    intervention_runs = []
    for raw_path in args.intervention_dirs:
        path = Path(raw_path).resolve()
        intervention_runs.append((_read_json(path / "plan.json"), _read_json(path / "report.json")))
    report = analyze_contribution_estimands(
        population_runs=population_runs,
        intervention_runs=intervention_runs,
        bootstrap_samples=args.bootstrap_samples,
        permutation_iterations=args.permutation_iterations,
        minimum_task_count=args.minimum_task_count,
        minimum_evaluation_records=args.minimum_evaluation_records,
        minimum_seed_replicates_per_role=args.minimum_seed_replicates_per_role,
    )
    _write_json(Path(args.output_path), report)
    if bool(args.contribution_manifest_path) != bool(args.authorization_output_path):
        raise ValueError(
            "Contribution manifest and authorization output paths must be supplied together"
        )
    if args.contribution_manifest_path:
        manifest = ContributionEstimationManifest.model_validate(
            _read_json(Path(args.contribution_manifest_path))
        )
        authorization = issue_contribution_production_authorization(
            analysis_report=report,
            manifest=manifest,
        )
        _write_json(
            Path(args.authorization_output_path),
            authorization.model_dump(mode="json"),
        )


if __name__ == "__main__":
    main()
