from __future__ import annotations

import copy
from typing import Any

import pytest

from trusted_synthesis.core.vtdo import (
    AnchoredEnergyConfig,
    ConditionalTrajectoryDistribution,
    ContributionApproximationAuthorization,
    StateValidityEstimate,
    ValidityRegion,
    ValidityThresholds,
    make_conditional_distribution,
    make_contribution_optimizer_update_contract,
    make_coverage_prior,
    make_gradient_projection_contribution_manifest,
    make_vtdo_role_contract,
    update_valid_trajectory_distribution,
    validate_contribution_approximation_authorization,
)
from trusted_synthesis.core.vtdo.schema import (
    contribution_approximation_authorization_id,
    state_validity_estimate_id,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_authorization_v2 import (
    _distribution_metrics,
    build_typed_authorization,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_contribution_materializer_v2 import (
    materialize_contribution_manifests,
)
from trusted_synthesis.hashing import canonical_hash


def _seal(values: dict[str, Any], *, field: str, prefix: str) -> dict[str, Any]:
    values[field] = canonical_hash(values, prefix=prefix)
    return values


def _authorization_inputs() -> dict[str, Any]:
    optimizer = make_contribution_optimizer_update_contract(
        learning_rate=2e-4,
        betas=(0.9, 0.999),
        epsilon=1e-8,
        maximum_gradient_norm=1.0,
        trainable_parameter_space="lora_adapter_parameters",
    ).model_dump(mode="json")
    task_distributions: dict[str, dict[str, Any]] = {}
    state_rows = []
    realization_counts = []
    jobs = []
    for task_index in range(30):
        task_id = f"task-{task_index:02d}"
        probability_profiles = (
            (0.2, 0.3, 0.5),
            (0.1, 0.2, 0.3, 0.4),
            (0.1, 0.15, 0.2, 0.25, 0.3),
        )
        probabilities = {
            f"{task_id}:{chr(ord('a') + state_index)}": probability
            for state_index, probability in enumerate(
                probability_profiles[task_index % len(probability_profiles)]
            )
        }
        distribution = make_conditional_distribution(
            task_id,
            probabilities,
            round_index=0,
        )
        task_distributions[task_id] = {
            "probabilities": probabilities,
            "distribution_id": distribution.distribution_id,
            "distribution": distribution.model_dump(mode="json"),
        }
        for state_id in probabilities:
            realization_ids = tuple(
                f"realization:{task_id}:{state_id}:{index}"
                for index in range(3)
            )
            state_rows.append(
                {
                    "task_id": task_id,
                    "state_id": state_id,
                    "realization_ids": realization_ids,
                }
            )
            realization_counts.append((task_id, state_id, 3))
            jobs.extend(
                {
                    "job_id": f"job:{task_id}:{state_id}:{index}",
                    "task_id": task_id,
                    "state_id": state_id,
                    "realization_id": realization_id,
                    "record_id": f"record:{task_id}:{state_id}:{index}",
                }
                for index, realization_id in enumerate(realization_ids)
            )
    record_ids = {
        role: tuple(f"record:{role}:{index:02d}" for index in range(16))
        for role in ("estimation", "validation", "authorization")
    }
    token_records = {
        job["record_id"]: {
            "common_label_positions": (1,),
            "differential_label_positions": (2,),
            "common_supervised_token_count": 1,
            "differential_supervised_token_count": 1,
            "differential_supervised_token_fraction": 0.5,
        }
        for job in jobs
    }
    token_task_rows = tuple(
        {
            "task_id": task_id,
            "record_count": sum(1 for job in jobs if job["task_id"] == task_id),
            "minimum_record_differential_supervised_token_fraction": 0.5,
            "mean_record_differential_supervised_token_fraction": 0.5,
            "pooled_differential_supervised_token_fraction": 0.5,
        }
        for task_id in task_distributions
    )
    token_state_rows = tuple(
        {
            "task_id": row["task_id"],
            "state_id": row["state_id"],
            "record_count": len(row["realization_ids"]),
            "minimum_record_differential_supervised_token_fraction": 0.5,
            "mean_record_differential_supervised_token_fraction": 0.5,
            "pooled_differential_supervised_token_fraction": 0.5,
        }
        for row in state_rows
    )
    token_region_manifest = _seal(
        {
            "version": "aligned_common_subsequence_token_gradient.v2",
            "coverage_gate_policy": "minimum_task_pooled_differential_supervised_tokens",
            "record_level_policy": "non_empty_regions_required_fraction_is_diagnostic",
            "minimum_task_pooled_differential_supervised_token_fraction_threshold": 0.05,
            "minimum_observed_record_differential_supervised_token_fraction": 0.5,
            "minimum_observed_state_pooled_differential_supervised_token_fraction": 0.5,
            "minimum_observed_task_pooled_differential_supervised_token_fraction": 0.5,
            "records": token_records,
            "state_rows": token_state_rows,
            "task_rows": token_task_rows,
            "status": "passed",
        },
        field="manifest_hash",
        prefix="finance_gradient_token_region_manifest:",
    )
    gradient_plan = _seal(
        {
            "beneficiary_model_state_id": "beneficiary:state",
            "beneficiary_checkpoint_hash": "beneficiary:checkpoint",
            "run_role": "production_candidate",
            "local_optimizer_contract": optimizer,
            "gradient_parameter_space": "lora_adapter_parameters",
            "task_distributions": task_distributions,
            "gradient_estimation_record_ids": record_ids["estimation"],
            "gradient_validation_record_ids": record_ids["validation"],
            "final_test_record_ids": record_ids["authorization"],
            "gradient_estimation_set_id": "objective:estimation",
            "gradient_validation_set_id": "objective:validation",
            "final_test_set_id": "objective:authorization",
            "task_sampling_contract_hash": "sampling:stratified-salted",
            "state_realization_manifest_hash": "realizations:fresh-v2",
            "state_realization_manifest": {
                "realization_counts": tuple(realization_counts),
            },
            "jobs": tuple(jobs),
            "token_region_decomposition": token_region_manifest,
            "token_audit": {
                job["record_id"]: {"supervised_tokens": 2}
                for job in jobs
            },
        },
        field="plan_hash",
        prefix="finance_contribution_gradient_plan:",
    )
    stability = {
        "status": "passed",
        "evidence_hash": "realization-stability:passed",
    }
    gradient_report = _seal(
        {
            "plan_hash": gradient_plan["plan_hash"],
            "task_count": 30,
            "state_count": len(state_rows),
            "state_rows": tuple(state_rows),
            "gradient_realization_stability": stability,
            "gradient_diagnostics_hash": stability["evidence_hash"],
            "token_region_manifest_hash": token_region_manifest["manifest_hash"],
            "uncertainty_penalty_coefficient": 1.0,
        },
        field="report_hash",
        prefix="finance_contribution_gradient_report:",
    )
    support_scaling = _seal(
        {
            "support_sizes": (4, 8, 16, 32),
            "selected_minimum_support_size": 16,
            "size_rows": tuple(
                {
                    "support_size": size,
                    "passes_stability_gate": size >= 16,
                }
                for size in (4, 8, 16, 32)
            ),
            "status": "passed",
        },
        field="report_hash",
        prefix="finance_objective_support_scaling_report:",
    )
    local_update = _seal(
        {
            "source_gradient_plan_hash": gradient_plan["plan_hash"],
            "source_gradient_report_hash": gradient_report["report_hash"],
            "beneficiary_model_state_id": "beneficiary:state",
            "beneficiary_checkpoint_hash": "beneficiary:checkpoint",
            "optimizer_contract": optimizer,
            "task_sampling_contract_hash": "sampling:stratified-salted",
            "state_realization_manifest_hash": "realizations:fresh-v2",
            "state_artifacts": tuple(
                {"task_id": row["task_id"], "state_id": row["state_id"]}
                for row in state_rows
            ),
            "state_jackknife_artifacts": tuple(
                {
                    "task_id": row["task_id"],
                    "state_id": row["state_id"],
                    "jackknife_id": (
                        f"jackknife:{row['task_id']}:{row['state_id']}:{index}"
                    ),
                    "excluded_realization_id": realization_id,
                }
                for row in state_rows
                for index, realization_id in enumerate(row["realization_ids"])
            ),
            "state_uncertainty_method": (
                "leave_one_realization_out_jackknife_pseudovalues"
            ),
        },
        field="manifest_hash",
        prefix="finance_gp_c_local_update_manifest:",
    )

    finite_plans: dict[str, dict[str, Any]] = {}
    directions: dict[str, dict[str, Any]] = {}
    finite_reports: dict[str, dict[str, Any]] = {}
    objective_manifests: dict[str, dict[str, Any]] = {}
    proxy_reports: dict[str, dict[str, Any]] = {}

    def add_role(role: str, prerequisites: dict[str, str]) -> None:
        objective_hash = f"objective-content:{role}"
        plan = _seal(
            {
                "source_gradient_plan_hash": gradient_plan["plan_hash"],
                "source_gradient_report_hash": gradient_report["report_hash"],
                "beneficiary_model_state_id": "beneficiary:state",
                "beneficiary_checkpoint_hash": "beneficiary:checkpoint",
                "objective_role": role,
                "objective_gradient_point": "post_global_update",
                "objective_record_ids": record_ids[role],
                "objective_records_hash": objective_hash,
                "objective_record_count": 16,
                "authorization_prerequisite_report_hashes": prerequisites,
            },
            field="plan_hash",
            prefix="finance_finite_target_plan:",
        )
        direction = _seal(
            {
                "finite_target_plan_hash": plan["plan_hash"],
                "source_gradient_plan_hash": gradient_plan["plan_hash"],
                "local_update_manifest_hash": local_update["manifest_hash"],
                "jackknife_state_count": len(state_rows),
            },
            field="manifest_hash",
            prefix="finance_gp_c_finite_target_directions:",
        )
        report = _seal(
            {
                "plan_hash": plan["plan_hash"],
                "source_gradient_plan_hash": gradient_plan["plan_hash"],
                "source_gradient_report_hash": gradient_report["report_hash"],
                "beneficiary_model_state_id": "beneficiary:state",
                "beneficiary_checkpoint_hash": "beneficiary:checkpoint",
                "objective_role": role,
                "objective_gradient_point": "post_global_update",
                "objective_record_ids": record_ids[role],
                "objective_records_hash": objective_hash,
                "objective_record_count": 16,
                "direction_manifest_hash": direction["manifest_hash"],
                "authorization_prerequisite_report_hashes": prerequisites,
                "development_gate_eligible": role in {"estimation", "validation"},
                "authorization_access_granted": role == "authorization",
                "status": "passed",
            },
            field="report_hash",
            prefix="finance_finite_target_report:",
        )
        objective = _seal(
            {
                "finite_target_plan_hash": plan["plan_hash"],
                "source_gradient_plan_hash": gradient_plan["plan_hash"],
                "local_update_manifest_hash": local_update["manifest_hash"],
                "beneficiary_model_state_id": "beneficiary:state",
                "beneficiary_checkpoint_hash": "beneficiary:checkpoint",
                "objective_role": role,
                "objective_gradient_point": "post_global_update",
                "objective_record_ids": record_ids[role],
                "objective_records_hash": objective_hash,
                "objective_record_count": 16,
            },
            field="manifest_hash",
            prefix="finance_post_global_objective_gradient_manifest:",
        )
        proxy_state_rows = []
        for task_index, (task_id, distribution) in enumerate(task_distributions.items()):
            probabilities = distribution["probabilities"]
            raw = tuple(float(index) for index in range(len(probabilities)))
            mean = sum(
                probability * value
                for probability, value in zip(probabilities.values(), raw, strict=True)
            )
            for (state_id, probability), value in zip(
                probabilities.items(), raw, strict=True
            ):
                centered = value - mean
                proxy_state_rows.append(
                    {
                        "task_id": task_id,
                        "task_type": "comparison" if task_index % 2 else "temporal",
                        "state_id": state_id,
                        "current_probability": probability,
                        "scaled_gp_c_proxy": centered,
                        "jackknife_raw_gp_c_proxy_values": (
                            centered - 0.01,
                            centered,
                            centered + 0.01,
                        ),
                        "jackknife_realization_ids": (
                            f"realization:{task_id}:{state_id}:0",
                            f"realization:{task_id}:{state_id}:1",
                            f"realization:{task_id}:{state_id}:2",
                        ),
                        "jackknife_realization_count": 3,
                        "jackknife_proxy_sample_standard_deviation": 0.01,
                        "finite_target": centered,
                    }
                )
        proxy = _seal(
            {
                "finite_target_plan_hash": plan["plan_hash"],
                "finite_target_report_hash": report["report_hash"],
                "source_gradient_plan_hash": gradient_plan["plan_hash"],
                "beneficiary_model_state_id": "beneficiary:state",
                "beneficiary_checkpoint_hash": "beneficiary:checkpoint",
                "local_update_manifest_hash": local_update["manifest_hash"],
                "objective_gradient_manifest_hash": objective["manifest_hash"],
                "objective_role": role,
                "objective_gradient_point": "post_global_update",
                "objective_record_ids": record_ids[role],
                "objective_records_hash": objective_hash,
                "objective_record_count": 16,
                "calibration_source": (
                    "fitted_on_estimation_only"
                    if role == "estimation"
                    else "frozen_estimation_scale"
                ),
                "applied_calibration_scale": 1.0,
                "state_rows": tuple(proxy_state_rows),
                "state_uncertainty_method": (
                    "leave_one_realization_out_jackknife_pseudovalues"
                ),
                "status": "passed",
            },
            field="report_hash",
            prefix="finance_post_global_gp_c_proxy_report:",
        )
        finite_plans[role] = plan
        directions[role] = direction
        finite_reports[role] = report
        objective_manifests[role] = objective
        proxy_reports[role] = proxy

    add_role("estimation", {})
    add_role("validation", {})
    prerequisites = {
        "estimation": finite_reports["estimation"]["report_hash"],
        "validation": finite_reports["validation"]["report_hash"],
    }
    add_role("authorization", prerequisites)
    return {
        "gradient_plan": gradient_plan,
        "gradient_report": gradient_report,
        "support_scaling_report": support_scaling,
        "local_update_manifest": local_update,
        "finite_target_plans": finite_plans,
        "direction_manifests": directions,
        "finite_target_reports": finite_reports,
        "proxy_reports": proxy_reports,
        "objective_gradient_manifests": objective_manifests,
    }


def test_typed_authorization_replays_the_complete_evidence_chain() -> None:
    inputs = _authorization_inputs()

    authorization = build_typed_authorization(**inputs)

    assert authorization.status == "authorized"
    assert authorization.objective_gradient_point == "post_global_update"
    assert authorization.local_update_manifest_hash == inputs["local_update_manifest"][
        "manifest_hash"
    ]
    assert authorization.task_count == 30
    assert authorization.state_count == 120
    assert {len(states) for _, states in authorization.task_state_supports} == {
        3,
        4,
        5,
    }


def test_typed_authorization_recomputes_token_region_task_coverage() -> None:
    inputs = _authorization_inputs()
    gradient_plan = copy.deepcopy(inputs["gradient_plan"])
    gradient_plan.pop("plan_hash")
    token_regions = copy.deepcopy(gradient_plan["token_region_decomposition"])
    token_regions.pop("manifest_hash")
    token_regions["task_rows"][0][
        "pooled_differential_supervised_token_fraction"
    ] = 0.4
    _seal(
        token_regions,
        field="manifest_hash",
        prefix="finance_gradient_token_region_manifest:",
    )
    gradient_plan["token_region_decomposition"] = token_regions
    _seal(
        gradient_plan,
        field="plan_hash",
        prefix="finance_contribution_gradient_plan:",
    )
    gradient_report = copy.deepcopy(inputs["gradient_report"])
    gradient_report.pop("report_hash")
    gradient_report["plan_hash"] = gradient_plan["plan_hash"]
    gradient_report["token_region_manifest_hash"] = token_regions["manifest_hash"]
    _seal(
        gradient_report,
        field="report_hash",
        prefix="finance_contribution_gradient_report:",
    )
    inputs["gradient_plan"] = gradient_plan
    inputs["gradient_report"] = gradient_report

    with pytest.raises(ValueError, match="token-region aggregate is invalid"):
        build_typed_authorization(**inputs)


def test_distribution_metrics_exclude_zero_gain_tasks_from_normalized_regret() -> None:
    rows = []
    for task_id, proxy, target in (
        ("task:zero-gain", (10.0, 0.0, -10.0), (0.0, 0.0, 0.0)),
        ("task:normalizable", (-1.0, 0.0, 1.0), (-1.0, 0.0, 1.0)),
    ):
        rows.extend(
            {
                "task_id": task_id,
                "task_type": "comparison",
                "state_id": f"{task_id}:{index}",
                "current_probability": 1.0 / 3.0,
                "scaled_gp_c_proxy": proxy[index],
                "finite_target": target[index],
            }
            for index in range(3)
        )

    metrics = _distribution_metrics(
        rows,
        temperature=1.0,
        normalizable_gain_floor=1e-6,
    )

    assert metrics["normalizable_task_count"] == 1
    assert metrics["normalizable_task_rate"] == pytest.approx(0.5)
    by_task = {row["task_id"]: row for row in metrics["task_rows"]}
    assert by_task["task:zero-gain"]["attainable_gain"] == pytest.approx(0.0)
    assert by_task["task:zero-gain"]["normalized_target_regret"] is None
    assert metrics["mean_normalized_target_regret"] == pytest.approx(0.0)


def test_typed_authorization_rejects_changed_partition_records() -> None:
    inputs = _authorization_inputs()
    objective = copy.deepcopy(inputs["objective_gradient_manifests"]["authorization"])
    objective.pop("manifest_hash")
    objective["objective_record_ids"] = (
        "record:validation:00",
        *objective["objective_record_ids"][1:],
    )
    _seal(
        objective,
        field="manifest_hash",
        prefix="finance_post_global_objective_gradient_manifest:",
    )
    inputs["objective_gradient_manifests"]["authorization"] = objective

    with pytest.raises(ValueError, match="changed objective records"):
        build_typed_authorization(**inputs)


def test_typed_authorization_rejects_early_authorization_access() -> None:
    inputs = _authorization_inputs()
    report = copy.deepcopy(inputs["finite_target_reports"]["authorization"])
    report.pop("report_hash")
    report["authorization_access_granted"] = False
    _seal(report, field="report_hash", prefix="finance_finite_target_report:")
    inputs["finite_target_reports"]["authorization"] = report
    proxy = copy.deepcopy(inputs["proxy_reports"]["authorization"])
    proxy.pop("report_hash")
    proxy["finite_target_report_hash"] = report["report_hash"]
    _seal(
        proxy,
        field="report_hash",
        prefix="finance_post_global_gp_c_proxy_report:",
    )
    inputs["proxy_reports"]["authorization"] = proxy

    with pytest.raises(ValueError, match="opened before frozen development gates"):
        build_typed_authorization(**inputs)


def _accepted_validity(task_id: str, state_id: str) -> StateValidityEstimate:
    thresholds = ValidityThresholds(reject_below=0.2, accept_at_or_above=0.8)
    values = {
        "task_condition_id": task_id,
        "state_id": state_id,
        "attempted_trajectory_count": 1,
        "valid_trajectory_count": 1,
        "estimated_validity": 1.0,
        "confidence_lower": 0.5,
        "confidence_upper": 1.0,
        "mean_component_validity": {"independent_verifier": 1.0},
        "thresholds": thresholds,
        "classification_statistic": "posterior_mean",
        "region": ValidityRegion.ACCEPTED,
        "estimator_id": "authorization-v2-test",
        "estimator_version": "2.0.0",
    }
    provisional = StateValidityEstimate.model_construct(estimate_id="pending", **values)
    return StateValidityEstimate(
        estimate_id=state_validity_estimate_id(provisional),
        **values,
    )


def test_authorization_materializes_core_manifests_and_drives_update() -> None:
    inputs = _authorization_inputs()
    authorization = build_typed_authorization(**inputs)

    manifests, report = materialize_contribution_manifests(
        gradient_plan=inputs["gradient_plan"],
        authorization=authorization,
        validation_proxy_report=inputs["proxy_reports"]["validation"],
    )

    assert report["status"] == "passed"
    assert len(manifests) == 30
    task_id = authorization.task_condition_ids[0]
    distribution = ConditionalTrajectoryDistribution.model_validate(
        inputs["gradient_plan"]["task_distributions"][task_id]["distribution"]
    )
    manifest = {value.task_condition_id: value for value in manifests}[task_id]
    states = tuple(distribution.probabilities)
    update = update_valid_trajectory_distribution(
        distribution,
        make_coverage_prior(
            task_id,
            {state_id: 1.0 / len(states) for state_id in states},
            policy="authorization-v2-test",
        ),
        tuple(_accepted_validity(task_id, state_id) for state_id in states),
        manifest,
        authorization,
        AnchoredEnergyConfig(
            epsilon=0.01,
            contribution_temperature=1.0,
            novelty_temperature=1.0,
            contribution_weight=0.9,
            novelty_weight=0.1,
            history_kl_weight=1.0,
            coverage_kl_weight=1.0,
        ),
        make_vtdo_role_contract(
            explorer_provider_id="explorer:v2-test",
            materialization_provider_id="materializer:v2-test",
            beneficiary_model_state_id=authorization.beneficiary_model_state_id,
            final_student_model_id="student:v2-test",
        ),
    )
    assert update.next_distribution.source_distribution_id == distribution.distribution_id
    assert update.next_distribution.estimator_manifest_hash == manifest.manifest_id


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("realization_id", "changed realization lineage"),
        ("sample_standard_deviation", "deviation failed replay"),
    ),
)
def test_materializer_rejects_changed_jackknife_lineage(
    mutation: str,
    message: str,
) -> None:
    inputs = _authorization_inputs()
    authorization = build_typed_authorization(**inputs)
    proxy = copy.deepcopy(inputs["proxy_reports"]["validation"])
    proxy.pop("report_hash")
    first = proxy["state_rows"][0]
    if mutation == "realization_id":
        first["jackknife_realization_ids"] = (
            "realization:foreign",
            *first["jackknife_realization_ids"][1:],
        )
    else:
        first["jackknife_proxy_sample_standard_deviation"] = 999.0
    _seal(
        proxy,
        field="report_hash",
        prefix="finance_post_global_gp_c_proxy_report:",
    )
    authorization_payload = {
        field: getattr(authorization, field)
        for field in ContributionApproximationAuthorization.model_fields
    }
    authorization_payload["proxy_report_hashes"] = tuple(
        (role, proxy["report_hash"] if role == "validation" else report_hash)
        for role, report_hash in authorization.proxy_report_hashes
    )
    authorization_payload["authorization_id"] = "pending"
    provisional = ContributionApproximationAuthorization.model_construct(
        **authorization_payload
    )
    authorization_payload["authorization_id"] = (
        contribution_approximation_authorization_id(provisional)
    )
    changed_authorization = ContributionApproximationAuthorization(
        **authorization_payload
    )

    with pytest.raises(ValueError, match=message):
        materialize_contribution_manifests(
            gradient_plan=inputs["gradient_plan"],
            authorization=changed_authorization,
            validation_proxy_report=proxy,
        )


def test_authorization_rejects_same_probabilities_from_another_round() -> None:
    inputs = _authorization_inputs()
    authorization = build_typed_authorization(**inputs)
    task_id = authorization.task_condition_ids[0]
    original = ConditionalTrajectoryDistribution.model_validate(
        inputs["gradient_plan"]["task_distributions"][task_id]["distribution"]
    )
    later = make_conditional_distribution(
        task_id,
        original.probabilities,
        round_index=original.round_index + 1,
        source_distribution_id=original.distribution_id,
    )
    manifest = make_gradient_projection_contribution_manifest(
        later,
        {
            state_id: (-0.01 + index, index, 0.01 + index)
            for index, state_id in enumerate(later.probabilities)
        },
        beneficiary_model_state_id=authorization.beneficiary_model_state_id,
        beneficiary_checkpoint_hash=authorization.beneficiary_checkpoint_hash,
        target_validation_set_id=dict(authorization.objective_partition_ids)[
            "validation"
        ],
        authorization_set_id=dict(authorization.objective_partition_ids)[
            "authorization"
        ],
        target_metric_id=authorization.target_metric_id,
        estimation_protocol_hash="cross-round-mutation",
        data_isolation_contract_id=authorization.strict_freshness_contract_hash,
        estimator_id=authorization.estimator_id,
        optimizer_contract=authorization.optimizer_contract,
        calibration_contract=authorization.calibration_contract,
        uncertainty_penalty_coefficient=authorization.uncertainty_penalty_coefficient,
    )

    with pytest.raises(ValueError, match="distribution ID"):
        validate_contribution_approximation_authorization(manifest, authorization)
