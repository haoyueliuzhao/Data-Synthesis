from __future__ import annotations

import pytest
from pydantic import ValidationError

from trusted_synthesis.domains.finance.capability_submechanism_runtime import (
    FinanceStoppingResolutionAction,
    FinanceStoppingShapeDecisionContract,
    FinanceSubmechanismEvidenceRole,
    FinanceSubmechanismScenario,
    make_finance_submechanism_scenario,
    public_submechanism_contract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_shape_redesign import (
    FinanceStoppingShapeRedesignReport,
    FrozenStoppingDifficultyPolicyV2,
    StoppingShapeRedesignResult,
    StoppingShapeRedesignTaskResponse,
    _redesign_shape_information_bootstrap,
    stopping_difficulty_policy_v2_id,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_shape_redesign_protocol import (
    ALL_SHAPES,
    FROZEN_POSITIVE_CONTROLS,
    REDESIGNED_FAILURE_SHAPES,
    STRUCTURAL_STRATA,
    StoppingShapeRedesignThresholds,
)


def _roles() -> tuple[FinanceSubmechanismEvidenceRole, ...]:
    return tuple(
        FinanceSubmechanismEvidenceRole(
            role_id=f"required_{index}",
            evidence_id=f"evidence:{index}",
            subject_alias=f"entity:{index}",
            metric_alias=f"metric:{index}",
            period_label=f"FY20{20 + index}",
        )
        for index in (1, 2)
    )


def _decision(kind: str) -> FinanceStoppingShapeDecisionContract:
    if kind == "partial_evidence_count_only":
        return FinanceStoppingShapeDecisionContract(
            contract_kind=kind,
            missing_role_disclosure="count_only",
        )
    if kind == "single_conflict_two_action_one_step":
        return FinanceStoppingShapeDecisionContract(
            contract_kind=kind,
            conflict_dimensions=("source_definition_compatibility",),
            available_resolution_actions=(
                FinanceStoppingResolutionAction(
                    tool_id="normalize_metric_unit_period",
                    applicable_when="source_definition_compatibility is conflicting",
                ),
                FinanceStoppingResolutionAction(
                    tool_id="open_document",
                    applicable_when="source authority or provenance is unresolved",
                ),
            ),
            resolution_step_count=1,
        )
    return FinanceStoppingShapeDecisionContract(
        contract_kind="standardized_relative_extra_call_cost",
        remaining_call_budget_fraction=0.25,
        remaining_token_budget_fraction=0.20,
        terminal_utility_loss=1.0,
    )


@pytest.mark.parametrize(
    ("payload", "expected_error"),
    (
        (
            {
                "contract_kind": "partial_evidence_count_only",
                "missing_role_disclosure": "count_only",
                "conflict_dimensions": ("source_definition_compatibility",),
            },
            "decision contract is inconsistent",
        ),
        (
            {
                "contract_kind": "single_conflict_two_action_one_step",
                "conflict_dimensions": ("source_definition_compatibility",),
                "available_resolution_actions": (
                    {
                        "tool_id": "normalize_metric_unit_period",
                        "applicable_when": "always",
                    },
                    {
                        "tool_id": "open_document",
                        "applicable_when": "source authority or provenance is unresolved",
                    },
                ),
                "resolution_step_count": 1,
            },
            "decision contract is inconsistent",
        ),
        (
            {
                "contract_kind": "standardized_relative_extra_call_cost",
                "remaining_call_budget_fraction": 0.50,
                "remaining_token_budget_fraction": 0.20,
                "terminal_utility_loss": 1.0,
            },
            "decision contract is inconsistent",
        ),
    ),
)
def test_shape_decision_contract_is_fail_closed(
    payload: dict[str, object],
    expected_error: str,
) -> None:
    with pytest.raises(ValidationError, match=expected_error):
        FinanceStoppingShapeDecisionContract.model_validate(payload)


def test_legacy_scenario_identity_omits_absent_v25_37_contract() -> None:
    scenario = make_finance_submechanism_scenario(
        submechanism_id="finance.test.legacy",
        parent_mechanism_id="finance.test.parent",
        intervention_kind="post_complete_cost",
        expected_host_events=("observe:complete", "resolve:stop"),
        evidence_roles=_roles(),
        public_resolution_hint="Finalize after verified completion.",
    )

    payload = scenario.model_dump(mode="json")

    assert "stopping_shape_decision_contract" not in payload
    assert FinanceSubmechanismScenario.model_validate(payload).scenario_id == scenario.scenario_id


@pytest.mark.parametrize(
    ("kind", "runtime_kind"),
    (
        ("partial_evidence_count_only", "incomplete_continue"),
        ("single_conflict_two_action_one_step", "evidence_conflict"),
        ("standardized_relative_extra_call_cost", "post_complete_cost"),
    ),
)
def test_public_projection_discloses_decision_semantics_not_internal_shape(
    kind: str,
    runtime_kind: str,
) -> None:
    scenario = make_finance_submechanism_scenario(
        submechanism_id=f"finance.test.{kind}",
        parent_mechanism_id="finance.test.parent",
        intervention_kind=runtime_kind,
        expected_host_events=("observe:decision", "resolve:decision"),
        evidence_roles=_roles(),
        public_resolution_hint="Use the typed public decision contract.",
        stopping_shape_decision_contract=_decision(kind),
    )

    public = public_submechanism_contract(scenario)
    decision = public["stopping_shape_decision_contract"]

    assert "contract_kind" not in decision
    assert decision["internal_shape_identity_disclosed"] is False
    assert kind not in str(public)


def _responses() -> tuple[StoppingShapeRedesignTaskResponse, ...]:
    return tuple(
        StoppingShapeRedesignTaskResponse(
            task_artifact_id=f"task:{stratum_index}:{instance_index}",
            stratum_id=stratum[0],
            stratum_instance_index=instance_index,
            realizations=(1, 0, 1, 0, 1, 0, 1, 0),
            probability=0.5,
            fisher_information=0.25,
        )
        for stratum_index, stratum in enumerate(STRUCTURAL_STRATA)
        for instance_index in (0, 1)
    )


def _shape_result(shape_id: str, *, admitted: bool) -> StoppingShapeRedesignResult:
    gates = {"scientific_gate": admitted}
    return StoppingShapeRedesignResult(
        shape_id=shape_id,
        shape_role="boundary_candidate",
        design_status=(
            "frozen_positive_control"
            if shape_id in FROZEN_POSITIVE_CONTROLS
            else "redesigned_failure_shape"
        ),
        task_responses=_responses(),
        mean_success_rate=0.5,
        minimum_task_probability=0.5,
        maximum_task_probability=0.5,
        between_task_probability_range=0.0,
        boundary_task_count=8,
        nonzero_information_task_count=8,
        total_fisher_information=2.0,
        effective_task_count=8.0,
        maximum_single_task_information_share=0.125,
        bootstrap_information_interval95=(1.0, 2.0),
        bootstrap_information_lcb=1.0,
        gate_results=gates,
        admitted=admitted,
        failure_codes=() if admitted else ("scientific_gate",),
    )


def _policy() -> FrozenStoppingDifficultyPolicyV2:
    values = {
        "source_contract_id": "contract:test",
        "shape_task_quotas": {shape_id: 8 for shape_id in ALL_SHAPES},
        "structural_strata": STRUCTURAL_STRATA,
        "thresholds": StoppingShapeRedesignThresholds(),
    }
    provisional = FrozenStoppingDifficultyPolicyV2.model_construct(
        policy_id="pending",
        **values,
    )
    return FrozenStoppingDifficultyPolicyV2(
        policy_id=stopping_difficulty_policy_v2_id(provisional),
        **values,
    )


def test_hierarchical_shape_bootstrap_is_deterministic_at_eight_tasks() -> None:
    thresholds = StoppingShapeRedesignThresholds(bootstrap_replicates=1_000)

    first = _redesign_shape_information_bootstrap(_responses(), thresholds, shape_id="shape:test")
    second = _redesign_shape_information_bootstrap(_responses(), thresholds, shape_id="shape:test")

    assert first == second
    assert first[0] > 0.0


def test_shape_result_rejects_incomplete_independent_task_pairing() -> None:
    payload = _shape_result("partial_required_evidence", admitted=True).model_dump(mode="json")
    payload["task_responses"] = payload["task_responses"][:-1]

    with pytest.raises(ValidationError, match="at least 8 items"):
        StoppingShapeRedesignResult.model_validate(payload)


def test_report_forbids_policy_freeze_when_a_positive_control_regresses() -> None:
    failed_control = sorted(FROZEN_POSITIVE_CONTROLS)[0]
    results = tuple(
        _shape_result(shape_id, admitted=shape_id != failed_control)
        for shape_id in sorted(ALL_SHAPES)
    )
    values = {
        "report_id": "pending",
        "contract_id": "contract:test",
        "recorded_rollout_count": 384,
        "execution_integrity_rate": 1.0,
        "terminal_resolution_rate": 1.0,
        "api_transport_resolution_rate": 1.0,
        "bounded_json_resolution_rate": 1.0,
        "observation_replay_rate": 1.0,
        "authority_integrity_rate": 1.0,
        "runtime_pathology_rate": 0.0,
        "l0_l2_failure_count": 0,
        "behavior_success_rate": 0.5,
        "primary_valid_success_rate": 0.5,
        "capability_contract_success_rate": 0.5,
        "runtime_measurement_ready": True,
        "shape_results": results,
        "positive_control_regression_count": 1,
        "redesigned_shape_admission_count": len(REDESIGNED_FAILURE_SHAPES),
        "all_shapes_admitted": False,
        "difficulty_policy": _policy(),
        "difficulty_policy_frozen": True,
        "api_call_count": 384,
        "total_model_tokens": 10_000,
        "estimated_cost_usd": 1.0,
        "discovered_models": ("DeepSeek-V4-Flash",),
        "failure_codes": ("positive_control_regression",),
        "fresh_three_population_preparation_authorized": False,
        "next_permitted_stage": "stopping_shape_redesign_only",
    }

    with pytest.raises(ValidationError, match="difficulty policy decision"):
        FinanceStoppingShapeRedesignReport.model_validate(values)
