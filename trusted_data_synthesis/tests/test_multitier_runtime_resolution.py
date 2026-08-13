from __future__ import annotations

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary_analysis import (
    CapabilityRolloutOutcome,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary_runner import (
    CapabilityBoundaryRolloutRecord,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_ladder import (
    DifficultyTier,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CAPABILITY_AXES,
    CAPABILITY_SENSITIVE_FAMILIES,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_confirmation import (
    WORKFLOW_RUNTIME_ARMS,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_runtime_resolution import (
    FailureLayer,
    FinanceRuntimeResolutionContract,
    RuntimeResolutionStage,
    RuntimeResolutionThresholds,
    RuntimeTerminalOutcome,
    TerminalClass,
    _classify_terminal,
    _prompt_diagnostics,
    make_runtime_resolution_report,
)
from trusted_synthesis.runtime.agent.schema import ModelCallTelemetry


def _record(
    *,
    status: str = "failed",
    error_type: str | None = "LLMClientError",
    error_message: str | None = None,
    telemetry: tuple[ModelCallTelemetry, ...] = (),
    verification_payload: dict[str, object] | None = None,
) -> CapabilityBoundaryRolloutRecord:
    return CapabilityBoundaryRolloutRecord.model_construct(
        record_id="record:test",
        status=status,
        error_type=error_type,
        error_message=error_message,
        telemetry=telemetry,
        failure_artifact=None,
        observations=(),
        verification_payload=verification_payload,
    )


def _outcome(*, valid: bool = False) -> CapabilityRolloutOutcome:
    return CapabilityRolloutOutcome.model_construct(valid_success=valid)


def _telemetry(
    *,
    http_success: bool = True,
    components: dict[str, int] | None = None,
) -> ModelCallTelemetry:
    return ModelCallTelemetry(
        provider="test",
        endpoint_host="example.test",
        model_requested="deepseek-v4-flash",
        request_hash="request:test",
        http_success=http_success,
        json_contract_success=http_success,
        response_shape={"prompt_component_bytes": components or {}},
    )


def test_success_is_l6_capability_outcome() -> None:
    result = _classify_terminal(
        _record(status="completed", error_type=None),
        _outcome(valid=True),
        prompt_pathology=False,
    )

    assert result[0] == TerminalClass.SUCCESSFUL_ANSWER
    assert result[1] == FailureLayer.L6_SUCCESS


def test_model_token_budget_is_model_decision_when_prompt_is_bounded() -> None:
    result = _classify_terminal(
        _record(
            error_message="Agent exceeded the frozen model-token budget",
            telemetry=(_telemetry(),),
        ),
        _outcome(),
        prompt_pathology=False,
    )

    assert result[0] == TerminalClass.MODEL_TOKEN_BUDGET
    assert result[1] == FailureLayer.L4_MODEL_AGENT_DECISION
    assert result[2] == ()


def test_model_token_budget_is_runtime_contract_when_prompt_is_pathological() -> None:
    result = _classify_terminal(
        _record(
            error_message="Agent exceeded the frozen model-token budget",
            telemetry=(_telemetry(),),
        ),
        _outcome(),
        prompt_pathology=True,
    )

    assert result[1] == FailureLayer.L1_TASK_RUNTIME_CONTRACT
    assert result[2] == (FailureLayer.L4_MODEL_AGENT_DECISION,)


def test_host_value_error_without_telemetry_is_not_mislabeled_as_provider_failure() -> None:
    result = _classify_terminal(
        _record(
            error_type="ValueError",
            error_message="operation contract contains malformed steps",
        ),
        _outcome(),
        prompt_pathology=False,
    )

    assert result[0] == TerminalClass.RUNTIME_CONTRACT_FAILURE
    assert result[1] == FailureLayer.L1_TASK_RUNTIME_CONTRACT


def test_prompt_diagnostics_preserve_component_boundaries() -> None:
    record = _record(
        telemetry=(
            _telemetry(
                components={
                    "instruction": 400,
                    "public_context.task": 2_000,
                    "public_context.observations": 3_000,
                    "contract_repair": 500,
                }
            ),
            _telemetry(
                components={
                    "instruction": 450,
                    "public_context.task": 2_100,
                    "public_context.observations": 4_000,
                }
            ),
        )
    )

    assert _prompt_diagnostics(record) == {
        "maximum_prompt_component_bytes": 4_000,
        "maximum_public_context_bytes": 6_100,
        "maximum_observation_summary_bytes": 4_000,
    }


def _terminal_outcomes(*, mixed_cell_count: int) -> tuple[RuntimeTerminalOutcome, ...]:
    values: list[RuntimeTerminalOutcome] = []
    cell_index = 0
    for family in CAPABILITY_SENSITIVE_FAMILIES:
        for tier in DifficultyTier:
            for runtime in WORKFLOW_RUNTIME_ARMS:
                for replicate in range(2):
                    failed = cell_index < mixed_cell_count and replicate == 1
                    semantic_correct = not failed or cell_index < 7
                    values.append(
                        RuntimeTerminalOutcome.model_construct(
                            terminal_outcome_id=f"terminal:{cell_index}:{replicate}",
                            contract_id="contract:test",
                            stage=RuntimeResolutionStage.HELDOUT_CONFIRMATION,
                            record_id=f"record:{cell_index}:{replicate}",
                            binding_id=f"binding:{cell_index}",
                            task_artifact_id=f"task:{cell_index // 2}",
                            family=family,
                            tier=tier,
                            runtime_arm=runtime,
                            replicate=replicate,
                            terminal_class=(
                                TerminalClass.INVALID_ANSWER
                                if failed
                                else TerminalClass.SUCCESSFUL_ANSWER
                            ),
                            primary_failure_layer=(
                                FailureLayer.L5_MODEL_SEMANTIC
                                if failed
                                else FailureLayer.L6_SUCCESS
                            ),
                            secondary_failure_layers=(),
                            attribution_confidence="high",
                            attribution_evidence=("typed_terminal",),
                            terminal_resolved=True,
                            failure_attributed=failed,
                            runtime_eligible_for_capability_denominator=True,
                            runtime_pathology=False,
                            prompt_pathology=False,
                            api_transport_resolved=True,
                            execution_integrity_passed=True,
                            raw_json_contract_success=True,
                            bounded_json_resolution_success=True,
                            observation_replay_success=True,
                            authority_integrity_success=True,
                            deterministic_valid=not failed,
                            semantic_answer_correct=semantic_correct,
                            valid_success=not failed,
                            capability_outcomes={
                                **{axis: not failed for axis in CAPABILITY_AXES},
                                "semantic": semantic_correct,
                                "final_valid": not failed,
                            },
                            stop_rejection_count=0,
                            identical_failed_action_block_count=0,
                            maximum_prompt_component_bytes=1_000,
                            maximum_public_context_bytes=2_000,
                            maximum_observation_summary_bytes=1_000,
                            api_call_count=1,
                            total_model_tokens=100,
                            estimated_cost_usd=0.001,
                            error_type="SemanticMismatch" if failed else None,
                            error_code="semantic_mismatch" if failed else None,
                        )
                    )
                cell_index += 1
    return tuple(values)


def _report_for(terminals: tuple[RuntimeTerminalOutcome, ...]):
    contract = FinanceRuntimeResolutionContract.model_construct(
        contract_id="contract:test",
        stage=RuntimeResolutionStage.HELDOUT_CONFIRMATION,
        requested_rollout_count=len(terminals),
        thresholds=RuntimeResolutionThresholds(),
    )
    return make_runtime_resolution_report(contract, terminals)


def test_semantic_accuracy_is_not_a_runtime_or_capability_ceiling_gate() -> None:
    report = _report_for(_terminal_outcomes(mixed_cell_count=13))

    assert report.metrics.semantic_accuracy_given_runtime_eligible > 0.90
    assert 0.10 <= report.metrics.valid_success_given_runtime_eligible <= 0.90
    assert report.runtime_qualification_passed
    assert report.capability_measurement_suitable
    assert report.joint_stage_ready
    assert report.information_matrix_evaluation_authorized


def test_saturated_capability_routes_to_support_redesign_not_runtime_repair() -> None:
    report = _report_for(_terminal_outcomes(mixed_cell_count=0))

    assert report.runtime_qualification_passed
    assert not report.capability_measurement_suitable
    assert not report.joint_stage_ready
    assert not report.information_matrix_evaluation_authorized
    assert report.next_permitted_stage == "capability_support_redesign_only"
