from __future__ import annotations

from types import SimpleNamespace

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_cross_population_stable_support import (  # noqa: E501
    FinanceCrossPopulationStableReport,
    PopulationStableGate,
    PopulationStableResult,
    TypedContextPopulationAudit,
    typed_retry_contract_rejections,
)


def _typed_contract() -> dict[str, object]:
    return {
        "observed_conflict_dimensions": ["source_definition_compatibility"],
        "available_resolution_actions": [
            {
                "tool_id": "normalize_metric_unit_period",
                "applicable_when": "source definitions are incompatible",
            },
            {
                "tool_id": "open_document",
                "applicable_when": "provenance coverage is incomplete",
            },
        ],
        "decision_rule": "Choose the action whose condition matches the observed conflict.",
        "required_prerequisite_action": None,
    }


def test_typed_retry_contract_is_order_invariant_and_fail_closed() -> None:
    available = {"normalize_metric_unit_period", "open_document"}
    contract = _typed_contract()

    assert not typed_retry_contract_rejections(
        contract, available_tool_ids=available
    )
    reversed_contract = dict(contract)
    reversed_contract["available_resolution_actions"] = list(
        reversed(contract["available_resolution_actions"])  # type: ignore[arg-type]
    )
    assert not typed_retry_contract_rejections(
        reversed_contract, available_tool_ids=available
    )

    missing_dimensions = dict(contract)
    missing_dimensions.pop("observed_conflict_dimensions")
    assert "missing_conflict_dimensions" in typed_retry_contract_rejections(
        missing_dimensions, available_tool_ids=available
    )

    unavailable = dict(contract)
    unavailable["available_resolution_actions"] = [
        *contract["available_resolution_actions"],  # type: ignore[misc]
        {
            "tool_id": "hidden_oracle_resolver",
            "applicable_when": "the hidden program selects it",
        },
    ]
    assert "unavailable_resolution_action" in typed_retry_contract_rejections(
        unavailable, available_tool_ids=available
    )


def test_typed_retry_contract_rejects_host_evidence_identity() -> None:
    contract = _typed_contract()
    contract["evidence_ids"] = ["evidence:secret"]

    failures = typed_retry_contract_rejections(
        contract,
        available_tool_ids={"normalize_metric_unit_period", "open_document"},
        evidence_ids={"evidence:secret"},
    )

    assert "host_secret_field_present" in failures
    assert "host_evidence_identity_present" in failures


def test_typed_context_audit_cannot_claim_ready_after_a_failed_mutation() -> None:
    audit = TypedContextPopulationAudit.model_construct(
        audit_id="pending",
        population_id="population:one",
        task_artifact_id="task:one",
        retry_contract_hash="hash:one",
        action_order_signature="order:one",
        action_count=3,
        stopping_shape_coverage_rate=1.0,
        missing_conflict_dimensions_rejected=False,
        action_order_permutation_accepted=True,
        unavailable_distractor_action_rejected=True,
        latest_typed_prerequisite_survives_repeated_failure=True,
        host_secret_injection_absent=True,
        ready=True,
    )

    with pytest.raises(ValueError, match="static audit decision"):
        audit.validate_audit()


def test_population_support_cannot_ignore_a_failed_population_gate() -> None:
    runtime = PopulationStableGate(
        gate_id="runtime",
        category="runtime",
        observed=1.0,
        requirement="=1",
        passed=True,
    )
    geometry = PopulationStableGate(
        gate_id="geometry",
        category="geometry",
        observed=0.0,
        requirement=">0",
        passed=False,
    )
    result = PopulationStableResult.model_construct(
        population_id="population:one",
        gates=(runtime, geometry),
        runtime_measurement_ready=True,
        capability_support_admitted=True,
        failure_codes=("geometry",),
    )

    with pytest.raises(ValueError, match="support decision"):
        result.validate_result()


def test_pooled_diagnostic_cannot_rescue_one_failed_population() -> None:
    populations = (
        SimpleNamespace(
            population_id="population:one",
            runtime_measurement_ready=True,
            capability_support_admitted=True,
        ),
        SimpleNamespace(
            population_id="population:two",
            runtime_measurement_ready=True,
            capability_support_admitted=False,
        ),
        SimpleNamespace(
            population_id="population:three",
            runtime_measurement_ready=True,
            capability_support_admitted=True,
        ),
    )
    report = FinanceCrossPopulationStableReport.model_construct(
        report_id="pending",
        requested_rollout_count=480,
        recorded_rollout_count=480,
        population_results=populations,
        pairwise_alignments=tuple(SimpleNamespace(passed=True) for _ in range(3)),
        static_typed_context_audit_passed=True,
        all_population_runtime_ready=True,
        all_population_capability_support_admitted=True,
        cross_population_alignment_ready=True,
        development_admitted=True,
        fresh_confirmation_preparation_authorized=True,
        next_permitted_stage="fresh_cross_population_stable_confirmation_preparation",
    )

    with pytest.raises(ValueError, match="support decision"):
        report.validate_report()
