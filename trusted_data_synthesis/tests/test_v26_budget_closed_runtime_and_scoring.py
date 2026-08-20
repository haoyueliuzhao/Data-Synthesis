from __future__ import annotations

import hashlib
from typing import Any

import pytest
from pydantic import ValidationError

from trusted_synthesis.core.trajectory.schema import (
    ActionType,
    StepStatus,
    Trajectory,
    TrajectoryStep,
    WorkflowKind,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_closed_instrument import (  # noqa: E501
    InstrumentFailureChannels,
    build_instrument_failure_channels,
    build_schema_closed_trace_sidecar,
    score_completed_trajectory,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.budget_closed import (
    BudgetClosedJsonClient,
    make_provider_token_budget_contract,
)
from trusted_synthesis.runtime.agent.client import LLMClientError
from trusted_synthesis.runtime.agent.schema import AgentModelConfig, ModelCallTelemetry

PLAN = (
    "Return only one compact JSON object with exactly these keys: plan_summary, "
    "subgoal_labels, stop_conditions."
)
DECISION = "Return only one compact JSON object. Choose one next public action."
FINAL = "Return only one JSON object with exactly rationale_summary, answer, and citations."
REPAIR = "\nCONTRACT_REPAIR_JSON:\n{}"


class _FixtureClient:
    def __init__(
        self,
        *,
        maximum_output_tokens: int,
        prompt_tokens: int = 1,
        completion_tokens: int = 1,
        total_tokens: int | None = 2,
    ) -> None:
        self.calls: list[str] = []
        self._prompt_tokens = prompt_tokens
        self._completion_tokens = completion_tokens
        self._total_tokens = total_tokens
        self._config = AgentModelConfig(
            provider="fixture",
            endpoint="https://fixture.invalid/v1/chat/completions",
            model="fixture-model",
            api_key_env="FIXTURE_API_KEY",
            max_output_tokens=maximum_output_tokens,
            maximum_model_attempts=1,
            fallback_models=(),
            require_requested_model=True,
        )

    @property
    def config(self) -> AgentModelConfig:
        return self._config

    def complete_json(self, prompt: str) -> tuple[dict[str, Any], ModelCallTelemetry]:
        self.calls.append(prompt)
        request_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        return {"value": 1}, ModelCallTelemetry(
            provider="fixture",
            endpoint_host="fixture.invalid",
            model_requested="fixture-model",
            model_selected="fixture-model",
            response_model="fixture-model",
            request_hash=request_hash,
            response_hash="response:fixture",
            http_status=200,
            http_success=True,
            json_contract_success=True,
            prompt_tokens=(self._prompt_tokens if self._total_tokens is not None else None),
            completion_tokens=(self._completion_tokens if self._total_tokens is not None else None),
            total_tokens=self._total_tokens,
        )


def _contract(
    *,
    maximum_total_tokens: int,
    maximum_prompt_utf8_bytes: int = 10_000,
    maximum_output_tokens: int = 4,
    envelope: int = 2,
    repair_reserve: int = 3,
    final_reserve: int = 5,
):
    return make_provider_token_budget_contract(
        provider="fixture",
        model_id="fixture-model",
        maximum_total_tokens=maximum_total_tokens,
        maximum_prompt_utf8_bytes=maximum_prompt_utf8_bytes,
        maximum_output_tokens=maximum_output_tokens,
        provider_chat_envelope_token_upper_bound=envelope,
        contract_repair_reserve_tokens=repair_reserve,
        final_answer_reserve_tokens=final_reserve,
    )


def _request_bound(prompt: str, *, output: int = 4, envelope: int = 2) -> int:
    return len(prompt.encode("utf-8")) + output + envelope


def test_exact_boundary_is_allowed_and_one_token_over_is_no_call() -> None:
    prompt = FINAL + REPAIR
    boundary = _request_bound(prompt)
    exact_provider = _FixtureClient(maximum_output_tokens=4)
    exact = BudgetClosedJsonClient(
        exact_provider,
        _contract(
            maximum_total_tokens=boundary,
            repair_reserve=0,
            final_reserve=0,
        ),
    )
    payload, _ = exact.complete_json(prompt)
    assert payload == {"value": 1}
    assert len(exact_provider.calls) == 1
    assert exact.audit().strict_budget_closed
    assert exact.audit().certificates[0].projected_upper_total == boundary

    over_provider = _FixtureClient(maximum_output_tokens=4)
    over = BudgetClosedJsonClient(
        over_provider,
        _contract(
            maximum_total_tokens=boundary - 1,
            repair_reserve=0,
            final_reserve=0,
        ),
    )
    with pytest.raises(LLMClientError, match="denied before construction"):
        over.complete_json(prompt)
    audit = over.audit()
    assert not over_provider.calls
    assert audit.strict_budget_closed
    assert audit.denied_no_call_count == 1
    assert audit.no_call_terminal is not None
    assert audit.no_call_terminal.reason_code == "request_bound_exceeds_remaining_budget"
    assert audit.no_call_terminal.denominator_retained
    assert not audit.no_call_terminal.instrument_failure


def test_changed_and_missing_usage_fail_closed_without_another_provider_call() -> None:
    changed_provider = _FixtureClient(
        maximum_output_tokens=4,
        prompt_tokens=1,
        completion_tokens=1,
        total_tokens=3,
    )
    changed = BudgetClosedJsonClient(
        changed_provider,
        _contract(maximum_total_tokens=1_000),
    )
    with pytest.raises(LLMClientError, match="budget Contract failed"):
        changed.complete_json(PLAN)
    changed_audit = changed.audit()
    assert changed_audit.status == "failed"
    assert "resource_budget:prompt_completion_sum_match" in (changed_audit.contract_failure_ids)
    with pytest.raises(LLMClientError, match="already failed"):
        changed.complete_json(PLAN)
    assert len(changed_provider.calls) == 1

    missing_provider = _FixtureClient(
        maximum_output_tokens=4,
        total_tokens=None,
    )
    missing = BudgetClosedJsonClient(
        missing_provider,
        _contract(maximum_total_tokens=1_000),
    )
    with pytest.raises(LLMClientError, match="budget Contract failed"):
        missing.complete_json(PLAN)
    assert missing.audit().status == "failed"
    assert "resource_budget:successful_usage_present" in (missing.audit().contract_failure_ids)
    assert len(missing_provider.calls) == 1


def test_oversized_prompt_and_both_reserve_shortfalls_are_typed_no_calls() -> None:
    oversized_provider = _FixtureClient(maximum_output_tokens=4)
    oversized = BudgetClosedJsonClient(
        oversized_provider,
        _contract(maximum_total_tokens=1_000, maximum_prompt_utf8_bytes=3),
    )
    with pytest.raises(LLMClientError):
        oversized.complete_json(PLAN)
    assert not oversized_provider.calls
    no_call_terminal = oversized.audit().no_call_terminal
    assert no_call_terminal is not None
    assert no_call_terminal.reason_code == "oversized_prompt"

    decision_bound = _request_bound(DECISION)
    final_reserve_provider = _FixtureClient(maximum_output_tokens=4)
    final_reserve = BudgetClosedJsonClient(
        final_reserve_provider,
        _contract(
            maximum_total_tokens=decision_bound + 3 + 5 - 1,
            repair_reserve=3,
            final_reserve=5,
        ),
    )
    with pytest.raises(LLMClientError):
        final_reserve.complete_json(DECISION)
    certificate = final_reserve.audit().certificates[0]
    assert certificate.denial_reason == "required_reserve_not_available"
    assert certificate.final_answer_reserve_tokens == 5
    assert not final_reserve_provider.calls

    final_bound = _request_bound(FINAL)
    repair_reserve_provider = _FixtureClient(maximum_output_tokens=4)
    repair_reserve = BudgetClosedJsonClient(
        repair_reserve_provider,
        _contract(
            maximum_total_tokens=final_bound + 3 - 1,
            repair_reserve=3,
            final_reserve=5,
        ),
    )
    with pytest.raises(LLMClientError):
        repair_reserve.complete_json(FINAL)
    certificate = repair_reserve.audit().certificates[0]
    assert certificate.denial_reason == "required_reserve_not_available"
    assert certificate.contract_repair_reserve_tokens == 3
    assert certificate.final_answer_reserve_tokens == 0
    assert not repair_reserve_provider.calls


def _trajectory() -> Trajectory:
    steps = (
        TrajectoryStep(
            step_index=1,
            action=ActionType.PLAN,
            rationale_summary="Plan.",
            status=StepStatus.SUCCEEDED,
        ),
        TrajectoryStep(
            step_index=2,
            action=ActionType.ANSWER,
            observation={"cited_evidence_ids": ["evidence:1"]},
            evidence_ids=("evidence:1",),
            rationale_summary="Answer.",
            status=StepStatus.SUCCEEDED,
        ),
    )
    values = {
        "task_id": "task:fixture",
        "workflow_kind": WorkflowKind.CANDIDATE,
        "steps": steps,
        "program_execution": {"execution_source": "fixture"},
        "final_answer": {
            "result": {"value": 1},
            "citations": [{"evidence_id": "evidence:1"}],
        },
        "generator_version": "fixture.v1",
    }
    return Trajectory(
        trajectory_id=canonical_hash(values, prefix="fixture_trajectory:"),
        **values,
    )


def test_schema_closed_sidecar_uses_real_fields_and_is_non_reclassifying() -> None:
    trajectory = _trajectory()
    sidecar = build_schema_closed_trace_sidecar(trajectory)
    assert sidecar.status == "passed"
    assert sidecar.nonexistent_field_access_count == 0
    assert "observation" in sidecar.trajectory_step_schema_fields
    assert "observation_id" not in sidecar.trajectory_step_schema_fields

    score = score_completed_trajectory(
        trajectory=trajectory,
        source_kind="model_generated",
        replay_result_id="replay:fixture",
        replay_passed=True,
        non_replay_checks={"answer_projection": True, "terminal_target": True},
        independent_valid=True,
        resource_budget_audit_id="budget:fixture",
        resource_budget_status="passed",
    )
    assert score.core_terminal == "valid_trajectory"
    assert score.instrument_admitted

    def fail_sidecar(_: Trajectory):
        raise AttributeError("TrajectoryStep has no observation_id")

    diagnostic_failure = score_completed_trajectory(
        trajectory=trajectory,
        source_kind="model_generated",
        replay_result_id="replay:fixture",
        replay_passed=True,
        non_replay_checks={"answer_projection": True, "terminal_target": True},
        independent_valid=True,
        resource_budget_audit_id="budget:fixture",
        resource_budget_status="passed",
        sidecar_builder=fail_sidecar,
    )
    assert diagnostic_failure.core_terminal == "valid_trajectory"
    assert diagnostic_failure.trace_sidecar is None
    assert not diagnostic_failure.failure_channels.report_complete
    assert not diagnostic_failure.instrument_admitted


def test_failure_namespaces_cannot_contaminate_raw_lineage() -> None:
    channels = build_instrument_failure_channels(
        raw_lineage_failures=("raw_lineage:missing_binding",),
        scoring_core_failures=("scoring_core:terminal_classifier",),
    )
    payload = channels.model_dump(mode="json")
    payload["raw_lineage_failures"] = ["scoring_core:terminal_classifier"]
    payload["channel_id"] = "finance_v26_budget_closed_failure_channels:tampered"
    with pytest.raises(ValidationError, match="another failure namespace"):
        InstrumentFailureChannels.model_validate(payload)
