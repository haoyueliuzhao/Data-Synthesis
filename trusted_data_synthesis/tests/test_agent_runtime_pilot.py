from __future__ import annotations

import pytest

from trusted_synthesis.domains.finance.agent_tools import (
    finance_archive_agent_tool_specs,
    make_finance_archive_agent_tool_manifest,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_agent_runtime_pilot import (
    AgentPilotArm,
    AgentPilotArmContract,
    AgentPilotTaskArmMetrics,
    AgentRuntimePilotThresholds,
    evaluate_agent_runtime_pilot,
    make_agent_runtime_pilot_contract,
)


def _manifest():
    return make_finance_archive_agent_tool_manifest(
        environment_id="finance_archive_pilot",
        corpus_id="finance_public_corpus",
        corpus_hash="finance_public_corpus_hash",
        archive_snapshot_id="finance_archive_snapshot",
        archive_snapshot_hash="finance_archive_snapshot_hash",
        maximum_tool_calls=8,
    )


def _arms(*, autonomous_token_budget: int = 8_000):
    return (
        AgentPilotArmContract(
            arm=AgentPilotArm.DIRECT_BARE,
            model_decision_authorities=("answer_generation",),
            host_decision_authorities=("validity_verification",),
            uses_tool_environment=False,
            token_budget=8_000,
            tool_call_budget=0,
        ),
        AgentPilotArmContract(
            arm=AgentPilotArm.SCRIPTED_TOOL,
            model_decision_authorities=("query_construction", "answer_generation"),
            host_decision_authorities=("tool_selection", "tool_execution"),
            uses_tool_environment=True,
            script_policy_hash="script_policy:test",
            token_budget=8_000,
            tool_call_budget=8,
        ),
        AgentPilotArmContract(
            arm=AgentPilotArm.AUTONOMOUS_AGENT,
            model_decision_authorities=(
                "tool_selection",
                "query_construction",
                "continue_or_stop",
                "failure_recovery",
                "answer_generation",
            ),
            host_decision_authorities=("tool_execution", "validity_verification"),
            uses_tool_environment=True,
            token_budget=autonomous_token_budget,
            tool_call_budget=8,
        ),
    )


def _thresholds() -> AgentRuntimePilotThresholds:
    return AgentRuntimePilotThresholds(
        minimum_validity_rate=0.75,
        maximum_validity_drop_vs_scripted=0.05,
        minimum_state_entropy_gain=0.05,
        minimum_accepted_state_gain=0.25,
        minimum_paired_diversity_task_fraction=0.5,
        minimum_nontrivial_agent_state_rate=0.1,
        minimum_tool_call_success_rate=0.9,
        minimum_evidence_provenance_completeness=0.95,
        minimum_stop_decision_quality_rate=0.8,
        near_mpe_ratio_threshold=0.5,
        minimum_near_mpe_rate_gain=0.05,
        minimum_meaningful_coordinate_rate_gain=0.05,
        minimum_differential_token_fraction=0.05,
        minimum_differential_gradient_fraction=0.05,
    )


def _task_population() -> tuple[dict[str, str], tuple[str, ...]]:
    families = {}
    target = []
    for family_index in range(6):
        family = f"family_{family_index}"
        for task_index in range(4):
            task_id = f"task_{family_index}_{task_index}"
            families[task_id] = family
            if task_index < 2:
                target.append(task_id)
    return families, tuple(target)


def _contract(*, autonomous_token_budget: int = 8_000):
    families, target = _task_population()
    return make_agent_runtime_pilot_contract(
        run_id="finance_agent_runtime_pilot:test",
        task_population_manifest_hash="task_population:test",
        task_family_by_id=families,
        exact_target_task_ids=target,
        model_config_hash="model:test",
        beneficiary_checkpoint_hash="beneficiary:test",
        validity_verifier_manifest_hash="validity_verifier:test",
        quotient_state_mapper_manifest_hash="quotient_state_mapper:test",
        exact_target_design_manifest_hash="exact_target_design:test",
        tool_environment=_manifest(),
        arms=_arms(autonomous_token_budget=autonomous_token_budget),
        unconditional_runs_per_task_arm=10,
        state_conditioned_attempts_per_state=5,
        explorer_identity="agent_explorer:test",
        trajectory_state_catalog_version="agent_state_catalog.v1",
        reachability_manifest_version="agent_reachability.v1",
        initial_distribution_version="agent_initial_distribution.v1",
        materialization_contract_version="agent_materialization.v1",
        excluded_population_manifest_hashes=("v22_bare_population:test",),
        thresholds=_thresholds(),
    )


def _metric(task_id: str, family: str, arm: AgentPilotArm, *, target: bool):
    values = {
        AgentPilotArm.DIRECT_BARE: {
            "valid": 8,
            "states": 2,
            "entropy": 0.4,
            "tools": (0, 0),
            "provenance": 0.7,
            "nontrivial": 0.0,
            "query": 0.0,
            "recovery": 0.0,
            "near": 0,
            "meaningful": 0,
            "tokens": 0.02,
            "gradients": 0.01,
        },
        AgentPilotArm.SCRIPTED_TOOL: {
            "valid": 9,
            "states": 3,
            "entropy": 0.8,
            "tools": (40, 38),
            "provenance": 0.97,
            "nontrivial": 0.08,
            "query": 0.05,
            "recovery": 0.02,
            "near": 1,
            "meaningful": 0,
            "tokens": 0.08,
            "gradients": 0.07,
        },
        AgentPilotArm.AUTONOMOUS_AGENT: {
            "valid": 9,
            "states": 4,
            "entropy": 1.2,
            "tools": (50, 48),
            "provenance": 0.99,
            "nontrivial": 0.4,
            "query": 0.2,
            "recovery": 0.1,
            "near": 2,
            "meaningful": 1,
            "tokens": 0.2,
            "gradients": 0.15,
        },
    }[arm]
    tool_count, tool_success = values["tools"]
    coordinate_count = 3 if target else 0
    return AgentPilotTaskArmMetrics(
        task_id=task_id,
        task_family=family,
        arm=arm,
        unconditional_run_count=10,
        valid_run_count=values["valid"],
        validity_rate=values["valid"] / 10,
        accepted_state_count=values["states"],
        natural_state_entropy=values["entropy"],
        decision_trace_diversity_rate=0.9,
        tool_call_count=tool_count,
        successful_tool_call_count=tool_success,
        failed_tool_call_count=tool_count - tool_success,
        tool_call_success_rate=tool_success / tool_count if tool_count else 0,
        query_reformulation_rate=values["query"],
        error_recovery_rate=values["recovery"],
        evidence_provenance_completeness=values["provenance"],
        verification_success_rate=0.9 if tool_count else 0,
        stop_decision_quality_rate=0.9,
        nontrivial_agent_state_rate=values["nontrivial"],
        off_target_transition_rate=0.1,
        state_conditioned_attempt_count=coordinate_count * 5,
        state_conditioned_on_target_rate=0.9,
        reachability_interval_mean_width=0.2,
        differential_token_fraction=values["tokens"],
        differential_gradient_fraction=values["gradients"],
        mean_update_vector_distance=0.1,
        exact_target_coordinate_count=coordinate_count,
        near_mpe_ratio_threshold=0.5,
        near_mpe_coordinate_count=values["near"] if target else 0,
        meaningful_coordinate_count=values["meaningful"] if target else 0,
    )


def _metrics(contract):
    return tuple(
        _metric(
            task_id,
            family,
            arm,
            target=task_id in contract.exact_target_task_ids,
        )
        for task_id, family in contract.task_family_by_id.items()
        for arm in AgentPilotArm
    )


def _evaluate(contract, metrics):
    return evaluate_agent_runtime_pilot(
        contract,
        metrics,
        arm_trajectory_manifest_hashes={
            arm: f"trajectory_manifest:{arm.value}" for arm in AgentPilotArm
        },
        state_catalog_manifest_hash="state_catalog:test",
        reachability_manifest_hash="reachability:test",
        exact_target_report_hash="exact_target:test",
    )


def test_finance_archive_tool_manifest_is_frozen_and_complete() -> None:
    manifest = _manifest()

    assert [item.tool_id for item in finance_archive_agent_tool_specs()] == [
        "search_archive",
        "open_document",
        "query_structured_fact",
        "calculator",
        "normalize_metric_unit_period",
        "cross_check_evidence",
    ]
    assert manifest.network_policy == "forbidden"
    assert manifest.manifest_id.startswith("agent_tool_environment:")
    assert all(item.host_executes for item in manifest.tools)
    assert all(item.content_addressed_observation for item in manifest.tools)


def test_agent_runtime_pilot_advances_only_after_all_gates_pass() -> None:
    contract = _contract()

    report = _evaluate(contract, _metrics(contract))

    assert report.status == "passed"
    assert report.decision == "advance_to_frontier_screening"
    assert report.next_permitted_stage == "beneficiary_frontier_screening"
    assert all(item.passed for item in report.gates)
    assert not report.gp_c_evaluated
    assert report.production_contribution == 0


def test_agent_runtime_pilot_stops_when_target_gain_is_absent() -> None:
    contract = _contract()
    rows = list(_metrics(contract))
    rows = [
        row.model_copy(
            update={
                "near_mpe_coordinate_count": 1,
                "meaningful_coordinate_count": 0,
            }
        )
        if row.arm == AgentPilotArm.AUTONOMOUS_AGENT and row.exact_target_coordinate_count
        else row
        for row in rows
    ]

    report = _evaluate(contract, tuple(rows))

    assert report.status == "failed"
    assert report.next_permitted_stage == "agent_environment_redesign"
    assert not next(
        item for item in report.gates if item.gate_id == "exact_target_sensitivity"
    ).passed


def test_agent_runtime_pilot_rejects_budget_or_metric_drift() -> None:
    with pytest.raises(ValueError, match="identical budgets"):
        _contract(autonomous_token_budget=8_001)

    contract = _contract()
    rows = _metrics(contract)
    with pytest.raises(ValueError, match="exactly cover"):
        _evaluate(contract, rows[:-1])

    changed = list(rows)
    changed[0] = changed[0].model_copy(update={"near_mpe_ratio_threshold": 0.6})
    with pytest.raises(ValueError, match="near-MPE threshold"):
        _evaluate(contract, tuple(changed))
