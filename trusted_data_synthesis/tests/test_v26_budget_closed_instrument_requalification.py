from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_closed_instrument_preflight import (  # noqa: E501
    BudgetClosedInstrumentContract,
    BudgetClosedInstrumentJobManifest,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_closed_instrument_requalification import (  # noqa: E501
    EXPECTED_CONTRACT_ID,
    EXPECTED_MANIFEST_ID,
    EXPECTED_PROVIDER_BUDGET_CONTRACT_ID,
    BudgetClosedExecutionBinding,
    BudgetClosedInstrumentRequalificationReport,
    BudgetClosedOnlineSourceReplayAudit,
    BudgetClosedRawProviderCall,
    _AttemptPromptJournalClient,
    _diagnostic,
    _execute_and_persist_raw,
    _RawFirstJournalClient,
    _score_with_failure_capture,
    prepare_budget_closed_instrument_execution,
    run_budget_closed_instrument_requalification,
)
from trusted_synthesis.runtime.agent.budget_closed import BudgetClosedJsonClient
from trusted_synthesis.runtime.agent.client import LLMClientError
from trusted_synthesis.runtime.agent.schema import AgentModelConfig, ModelCallTelemetry

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = PACKAGE_ROOT / "artifacts" / "vtdo_experiment"
TASK_SOURCE = (
    ARTIFACT_ROOT / "finance_v26_82_budget_closed_verifier_bound_instrument_population_v2_20260820"
)
VERIFIER_QUALIFICATION = (
    ARTIFACT_ROOT / "finance_v26_75_authority_preserving_verifier_qualification_v2_20260819"
)
PREFLIGHT = (
    ARTIFACT_ROOT / "finance_v26_83_budget_closed_verifier_bound_instrument_preflight_v2_20260820"
)
FORMAL = (
    ARTIFACT_ROOT
    / "finance_v26_84_budget_closed_verifier_bound_instrument_requalification_20260820"
)
RUN_ID = "finance_v26_84_budget_closed_verifier_bound_instrument_requalification_20260820"
PREPARED_FILES = (
    "execution_binding.json",
    "frozen_execution_contract.json",
    "frozen_job_manifest.json",
    "online_source_replay_audit.json",
)


def _prepare(output: Path) -> Any:
    return prepare_budget_closed_instrument_execution(
        execution_run_id=RUN_ID,
        task_source_dir=TASK_SOURCE,
        verifier_qualification_dir=VERIFIER_QUALIFICATION,
        preflight_dir=PREFLIGHT,
        output_dir=output,
        package_root=PACKAGE_ROOT,
    )


@pytest.fixture(scope="module")
def prepared(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Any]:
    output = tmp_path_factory.mktemp("v26_84_prepare")
    return output, _prepare(output)


def test_v26_84_pre_api_binding_is_deterministic(
    prepared: tuple[Path, Any],
    tmp_path: Path,
) -> None:
    output, values = prepared
    duplicate = tmp_path / "duplicate"
    duplicate_values = _prepare(duplicate)
    for relative in PREPARED_FILES:
        assert (output / relative).read_bytes() == (duplicate / relative).read_bytes()

    binding = BudgetClosedExecutionBinding.model_validate_json(
        (output / "execution_binding.json").read_text(encoding="utf-8")
    )
    replay = BudgetClosedOnlineSourceReplayAudit.model_validate_json(
        (output / "online_source_replay_audit.json").read_text(encoding="utf-8")
    )
    assert binding == values.execution_binding == duplicate_values.execution_binding
    assert replay == values.source_audit == duplicate_values.source_audit
    assert replay.replayed_file_count == replay.replay_pass_count
    assert replay.replayed_file_count >= 67
    assert binding.expected_job_count == 32
    assert binding.model_id == "deepseek-v4-flash"
    assert not binding.fallback_models
    assert binding.maximum_total_model_tokens_per_rollout == 120000
    assert binding.maximum_total_estimated_cost_usd == 2.0
    assert binding.pre_call_budget_certificate_required
    assert binding.typed_no_call_terminal_retained
    assert binding.provider_and_host_telemetry_separately_bound
    assert binding.shared_completed_trajectory_scorer_required


def test_v26_84_executes_exact_frozen_manifest(prepared: tuple[Path, Any]) -> None:
    output, _ = prepared
    contract = BudgetClosedInstrumentContract.model_validate_json(
        (output / "frozen_execution_contract.json").read_text(encoding="utf-8")
    )
    manifest = BudgetClosedInstrumentJobManifest.model_validate_json(
        (output / "frozen_job_manifest.json").read_text(encoding="utf-8")
    )
    assert contract.contract_id == EXPECTED_CONTRACT_ID
    assert manifest.manifest_id == EXPECTED_MANIFEST_ID
    assert contract.provider_token_budget_contract.contract_id == (
        EXPECTED_PROVIDER_BUDGET_CONTRACT_ID
    )
    assert len(manifest.jobs) == 32
    assert {item.empirical_role for item in manifest.jobs} == {"instrument_requalification"}
    assert {item.sampling_mode for item in manifest.jobs} == {"instrument_unconditional"}
    assert (output / "frozen_job_manifest.json").read_bytes() == (
        PREFLIGHT / "job_manifest.json"
    ).read_bytes()


class _FixtureProviderClient:
    def __init__(self, config: AgentModelConfig) -> None:
        self.config = config
        self.call_count = 0

    def discover_models(self) -> tuple[str, ...]:
        return (self.config.model,)

    def complete_json(self, prompt: str) -> tuple[dict[str, Any], ModelCallTelemetry]:
        self.call_count += 1
        if prompt.startswith(
            "Return only one compact JSON object with exactly these keys: plan_summary"
        ):
            payload: dict[str, Any] = {
                "plan_summary": "Attempt the public task.",
                "subgoal_labels": ["inspect", "verify"],
                "stop_conditions": ["Emit a supported answer."],
            }
        elif prompt.startswith(
            "Return only one JSON object with exactly rationale_summary, answer"
        ):
            payload = {
                "rationale_summary": "Fixture early stop.",
                "answer": {},
                "cited_evidence_ids": ["evidence:fixture"],
            }
        else:
            payload = {
                "decision_type": "final_answer",
                "rationale_summary": "Fixture early stop.",
                "answer": {},
                "cited_evidence_ids": ["evidence:fixture"],
            }
        response_text = json.dumps(payload, sort_keys=True)
        telemetry = ModelCallTelemetry(
            provider="deepseek",
            endpoint_host="api.deepseek.com",
            model_requested="deepseek-v4-flash",
            model_selected="deepseek-v4-flash",
            response_model="deepseek-v4-flash",
            request_hash=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            response_hash=hashlib.sha256(response_text.encode("utf-8")).hexdigest(),
            http_status=200,
            http_success=True,
            json_contract_success=True,
            finish_reason="stop",
            response_content_length=len(response_text),
            prompt_tokens=10,
            prompt_cache_hit_tokens=0,
            prompt_cache_miss_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            estimated_cost=0.0000028,
            cost_estimation_method="provider_cache_breakdown",
        )
        return payload, telemetry


def test_provider_payload_is_raw_first_and_precertified(
    prepared: tuple[Path, Any],
    tmp_path: Path,
) -> None:
    _, values = prepared
    config = AgentModelConfig.model_validate(values.contract.model_invocation_config)
    fixture = _FixtureProviderClient(config)
    recorder = _RawFirstJournalClient(
        fixture,
        execution_binding=values.execution_binding,
        job=values.manifest.jobs[0],
        output_dir=tmp_path,
    )
    budget = BudgetClosedJsonClient(
        recorder,
        values.contract.provider_token_budget_contract,
    )
    attempts = _AttemptPromptJournalClient(budget)
    prompt = "Return only one compact JSON object. Choose one next public action."
    response, telemetry = attempts.complete_json(prompt)
    audit = budget.audit()
    assert response["decision_type"] == "final_answer"
    assert fixture.call_count == 1
    assert recorder.telemetry == [telemetry]
    assert attempts.prompts == [prompt]
    assert audit.status == "passed"
    assert audit.provider_call_count == audit.permitted_request_count == 1
    assert audit.certificates[0].provider_call_permitted
    path = tmp_path / recorder.descriptors[0].relative_path
    artifact = BudgetClosedRawProviderCall.model_validate_json(path.read_text(encoding="utf-8"))
    assert artifact.response_payload == response
    assert artifact.prompt == prompt
    assert artifact.captured_before_budget_usage_validation
    assert artifact.captured_before_agent_contract_scoring


def test_oversized_prompt_produces_typed_no_call(
    prepared: tuple[Path, Any],
) -> None:
    _, values = prepared
    config = AgentModelConfig.model_validate(values.contract.model_invocation_config)
    fixture = _FixtureProviderClient(config)
    budget = BudgetClosedJsonClient(
        fixture,
        values.contract.provider_token_budget_contract,
    )
    with pytest.raises(LLMClientError, match="denied before construction"):
        budget.complete_json("x" * 60001)
    audit = budget.audit()
    assert fixture.call_count == 0
    assert audit.status == "passed"
    assert audit.provider_call_count == 0
    assert audit.denied_no_call_count == 1
    assert audit.no_call_terminal is not None
    assert audit.no_call_terminal.reason_code == "oversized_prompt"
    assert audit.no_call_terminal.denominator_retained
    assert not audit.no_call_terminal.instrument_failure


def test_fixture_agent_model_failure_is_retained_and_replayable(
    prepared: tuple[Path, Any],
    tmp_path: Path,
) -> None:
    _, values = prepared
    job = values.manifest.jobs[0]
    records = {item.record_id: item for item in values.records}
    environments = {item.manifest_id: item for item in values.environments}
    bindings = {item.contract_id: item for item in values.bindings}
    record = records[job.task_record_id]
    environment = environments[job.environment_manifest_id]
    config = AgentModelConfig.model_validate(values.contract.model_invocation_config)
    fixture = _FixtureProviderClient(config)
    raw = _execute_and_persist_raw(
        job=job,
        contract=values.contract,
        execution_binding=values.execution_binding,
        record=record,
        environment=environment,
        client=fixture,
        output_dir=tmp_path,
    )
    assert raw.execution_kind == "captured_model_contract_failure"
    assert raw.failure_artifact is not None
    assert raw.provider_budget_audit.status == "passed"
    assert raw.provider_budget_audit.provider_call_count == fixture.call_count
    assert raw.provider_request_prompts == raw.host_request_prompts
    assert len(raw.attempted_model_prompts) == len(raw.provider_request_prompts)

    rollout = _score_with_failure_capture(
        job=job,
        contract=values.contract,
        execution_binding=values.execution_binding,
        replay_contract=values.replay_contract,
        record=record,
        environment=environment,
        raw=raw,
        output_dir=tmp_path,
    )
    assert rollout.terminal_category == "model_invalid_trajectory"
    assert rollout.core_terminal == "invalid_trajectory"
    assert rollout.replay_result is not None and rollout.replay_result.passed
    assert rollout.non_replay_gate_audit is not None
    assert rollout.completed_trajectory_score is None
    assert rollout.instrument_admitted
    assert rollout.denominator_retained
    diagnostic = _diagnostic(
        rollout=rollout,
        raw=raw,
        record=record,
        binding=bindings[job.replay_binding_contract_id],
    )
    assert diagnostic.replay_passed
    assert diagnostic.non_replay_gate_audit_present
    assert diagnostic.authority_contract_in_initial_prompt
    assert diagnostic.terminal_target_in_initial_prompt
    assert diagnostic.instrument_admitted


def test_fixture_full_manifest_is_instrument_ready_and_zero_generation_replayable(
    tmp_path: Path,
) -> None:
    output = tmp_path / "fixture_full_manifest"
    clients: list[_FixtureProviderClient] = []

    def client_factory(config: AgentModelConfig) -> _FixtureProviderClient:
        client = _FixtureProviderClient(config)
        clients.append(client)
        return client

    report = run_budget_closed_instrument_requalification(
        execution_run_id=RUN_ID,
        task_source_dir=TASK_SOURCE,
        verifier_qualification_dir=VERIFIER_QUALIFICATION,
        preflight_dir=PREFLIGHT,
        output_dir=output,
        package_root=PACKAGE_ROOT,
        workers=8,
        client_factory=client_factory,
    )
    assert len(clients) == 1
    assert report.completed_rollout_count == 32
    assert report.model_outcome_count == 32
    assert report.model_valid_trajectory_count == 0
    assert report.model_invalid_trajectory_count == 32
    assert report.budget_exhausted_no_call_count == 0
    assert report.runtime_failure_count == 0
    assert report.instrument_gate_failure_count == 0
    assert report.report_completeness_failure_count == 0
    assert report.replay_pass_count == 32
    assert report.raw_lineage_audit.status == "passed"
    assert report.resource_budget_passed
    assert report.instrument_ready
    assert report.status == "passed"

    report_bytes = (output / "report.json").read_bytes()

    def fail_client(_: AgentModelConfig) -> Any:
        raise AssertionError("completed fixture replay constructed a model client")

    replayed = run_budget_closed_instrument_requalification(
        execution_run_id=RUN_ID,
        task_source_dir=TASK_SOURCE,
        verifier_qualification_dir=VERIFIER_QUALIFICATION,
        preflight_dir=PREFLIGHT,
        output_dir=output,
        package_root=PACKAGE_ROOT,
        workers=2,
        client_factory=fail_client,
    )
    assert replayed.report_id == report.report_id
    assert (output / "report.json").read_bytes() == report_bytes


def test_formal_v26_84_result_and_authorization() -> None:
    if not (FORMAL / "report.json").exists():
        pytest.skip("formal v26.84 online execution has not completed yet")
    report = BudgetClosedInstrumentRequalificationReport.model_validate_json(
        (FORMAL / "report.json").read_text(encoding="utf-8")
    )
    assert report.completed_rollout_count == report.expected_rollout_count == 32
    assert report.model_outcome_count == 32
    assert report.runtime_failure_count == 0
    assert report.instrument_gate_failure_count == 0
    assert report.report_completeness_failure_count == 0
    assert report.exact_requested_model_count == 32
    assert report.fallback_count == 0
    assert report.replay_pass_count == 32
    assert report.replay_failure_count == 0
    assert report.raw_lineage_audit.status == "passed"
    assert report.raw_lineage_audit.raw_before_scoring_pass_count == 32
    assert report.resource_budget_passed
    assert report.instrument_ready
    assert report.status == "passed"
    assert report.next_permitted_stage == ("fresh_capability_and_reachability_protocol_design_only")
    assert not report.capability_development_execution_authorized
    assert not report.state_reachability_execution_authorized
    assert not report.capability_support_evaluated
    assert not report.state_reachability_evaluated
    assert report.state_mapping_count == report.released_realization_count == 0
    assert report.production_contribution == 0


def test_completed_run_replay_constructs_no_model_client() -> None:
    if not (FORMAL / "report.json").exists():
        pytest.skip("formal v26.84 online execution has not completed yet")
    report_before = (FORMAL / "report.json").read_bytes()

    def fail_client(_: AgentModelConfig) -> Any:
        raise AssertionError("completed-run replay constructed a model client")

    report = run_budget_closed_instrument_requalification(
        execution_run_id=RUN_ID,
        task_source_dir=TASK_SOURCE,
        verifier_qualification_dir=VERIFIER_QUALIFICATION,
        preflight_dir=PREFLIGHT,
        output_dir=FORMAL,
        package_root=PACKAGE_ROOT,
        workers=2,
        client_factory=fail_client,
    )
    assert report.completed_rollout_count == 32
    assert report.instrument_ready
    assert (FORMAL / "report.json").read_bytes() == report_before
