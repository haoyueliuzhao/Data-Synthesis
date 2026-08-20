from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_verifier_bound_instrument_preflight import (  # noqa: E501
    VerifierBoundInstrumentContract,
    VerifierBoundInstrumentJobManifest,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_verifier_bound_instrument_requalification import (  # noqa: E501
    EXPECTED_CONTRACT_ID,
    EXPECTED_MANIFEST_ID,
    NON_REPLAY_CHECK_IDS,
    OnlineNonReplayGateAudit,
    OnlineSourceReplayAudit,
    RawProviderCallArtifact,
    VerifierBoundInstrumentExecutionBinding,
    VerifierBoundInstrumentRequalificationReport,
    _RawFirstJournalClient,
    online_non_replay_gate_audit_id,
    prepare_verifier_bound_instrument_execution,
    raw_provider_call_artifact_id,
    run_verifier_bound_instrument_requalification,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig, ModelCallTelemetry

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = PACKAGE_ROOT / "artifacts" / "vtdo_experiment"
TASK_SOURCE = ARTIFACT_ROOT / "finance_v26_76_verifier_bound_instrument_population_20260819"
VERIFIER_QUALIFICATION = (
    ARTIFACT_ROOT / "finance_v26_75_authority_preserving_verifier_qualification_v2_20260819"
)
PREFLIGHT = ARTIFACT_ROOT / "finance_v26_77_verifier_bound_instrument_preflight_20260819"
FORMAL = ARTIFACT_ROOT / "finance_v26_78_verifier_bound_instrument_requalification_20260820"
RUN_ID = "finance_v26_78_verifier_bound_instrument_requalification_20260820"
EXPECTED_BINDING_ID = (
    "finance_v26_verifier_bound_instrument_execution_binding:"
    "27250c6b577243a7c87f321c72877dd7ff3ccfaa0d5ea48a92d7a6db6eda2ae2"
)
EXPECTED_SOURCE_AUDIT_ID = (
    "finance_v26_verifier_bound_online_source_replay:"
    "3ac3660b7884fb0afeb5c5c7c809a577e73ce9f819adc8ad32016ffb1d72d766"
)
PREPARED_FILES = (
    "execution_binding.json",
    "frozen_execution_contract.json",
    "frozen_job_manifest.json",
    "online_source_replay_audit.json",
)


def _prepare(output: Path) -> None:
    prepare_verifier_bound_instrument_execution(
        execution_run_id=RUN_ID,
        task_source_dir=TASK_SOURCE,
        verifier_qualification_dir=VERIFIER_QUALIFICATION,
        preflight_dir=PREFLIGHT,
        output_dir=output,
        package_root=PACKAGE_ROOT,
    )


@pytest.fixture(scope="module")
def prepared(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("v26_78_prepare")
    _prepare(output)
    return output


def test_v26_78_pre_api_binding_is_deterministic(
    prepared: Path,
    tmp_path: Path,
) -> None:
    duplicate = tmp_path / "duplicate"
    _prepare(duplicate)
    for relative in PREPARED_FILES:
        assert (prepared / relative).read_bytes() == (duplicate / relative).read_bytes()

    binding = VerifierBoundInstrumentExecutionBinding.model_validate_json(
        (prepared / "execution_binding.json").read_text(encoding="utf-8")
    )
    replay = OnlineSourceReplayAudit.model_validate_json(
        (prepared / "online_source_replay_audit.json").read_text(encoding="utf-8")
    )
    assert binding.binding_id == EXPECTED_BINDING_ID
    assert replay.audit_id == EXPECTED_SOURCE_AUDIT_ID
    assert replay.replayed_file_count == replay.replay_pass_count == 67
    assert len(binding.implementation_source_files) == 17
    assert binding.expected_job_count == 32
    assert binding.model_id == "deepseek-v4-flash"
    assert not binding.fallback_models
    assert binding.maximum_total_model_tokens_per_rollout == 120000
    assert binding.maximum_total_estimated_cost_usd == 2.0
    assert binding.raw_provider_calls_persisted_before_agent_contract_scoring
    assert binding.raw_execution_persisted_before_verifier_replay_and_scoring
    assert binding.compiler_witness_empirical_count == 0
    assert binding.historical_diagnostic_candidate_count == 0


def test_v26_78_executes_the_exact_frozen_manifest(prepared: Path) -> None:
    contract = VerifierBoundInstrumentContract.model_validate_json(
        (prepared / "frozen_execution_contract.json").read_text(encoding="utf-8")
    )
    manifest = VerifierBoundInstrumentJobManifest.model_validate_json(
        (prepared / "frozen_job_manifest.json").read_text(encoding="utf-8")
    )
    assert contract.contract_id == EXPECTED_CONTRACT_ID
    assert manifest.manifest_id == EXPECTED_MANIFEST_ID
    assert len(manifest.jobs) == 32
    assert {item.empirical_role for item in manifest.jobs} == {"instrument_requalification"}
    assert {item.sampling_mode for item in manifest.jobs} == {"instrument_unconditional"}
    assert (prepared / "frozen_job_manifest.json").read_bytes() == (
        PREFLIGHT / "job_manifest.json"
    ).read_bytes()


class _FakeClient:
    def __init__(self, config: AgentModelConfig) -> None:
        self.config = config

    def complete_json(self, prompt: str) -> tuple[dict[str, Any], ModelCallTelemetry]:
        payload = {"decision_type": "unit_test"}
        telemetry = ModelCallTelemetry(
            provider="deepseek",
            endpoint_host="api.deepseek.com",
            model_requested="deepseek-v4-flash",
            model_selected="deepseek-v4-flash",
            response_model="deepseek-v4-flash",
            request_hash=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            response_hash="a" * 64,
            http_status=200,
            http_success=True,
            json_contract_success=True,
            finish_reason="stop",
            response_content_length=29,
            prompt_tokens=10,
            prompt_cache_hit_tokens=0,
            prompt_cache_miss_tokens=10,
            completion_tokens=3,
            total_tokens=13,
            estimated_cost=0.00000224,
            cost_estimation_method="provider_cache_breakdown",
        )
        return payload, telemetry


def test_raw_provider_payload_is_written_before_agent_scoring(
    prepared: Path,
    tmp_path: Path,
) -> None:
    binding = VerifierBoundInstrumentExecutionBinding.model_validate_json(
        (prepared / "execution_binding.json").read_text(encoding="utf-8")
    )
    contract = VerifierBoundInstrumentContract.model_validate_json(
        (prepared / "frozen_execution_contract.json").read_text(encoding="utf-8")
    )
    manifest = VerifierBoundInstrumentJobManifest.model_validate_json(
        (prepared / "frozen_job_manifest.json").read_text(encoding="utf-8")
    )
    config = AgentModelConfig.model_validate(contract.model_invocation_config)
    recorder = _RawFirstJournalClient(
        _FakeClient(config),
        execution_binding=binding,
        job=manifest.jobs[0],
        output_dir=tmp_path,
    )
    prompt = "raw-first unit prompt"
    response, telemetry = recorder.complete_json(prompt)
    assert response == {"decision_type": "unit_test"}
    assert recorder.telemetry == [telemetry]
    assert len(recorder.descriptors) == 1
    path = tmp_path / recorder.descriptors[0].relative_path
    artifact = RawProviderCallArtifact.model_validate_json(path.read_text(encoding="utf-8"))
    assert artifact.response_payload == response
    assert artifact.prompt == prompt
    assert artifact.captured_before_agent_contract_scoring
    assert artifact.provider_call_id


def test_online_contract_models_fail_closed_on_identity_or_gate_mutation(
    prepared: Path,
) -> None:
    binding_payload = json.loads((prepared / "execution_binding.json").read_text(encoding="utf-8"))
    binding_payload["contract_id"] = "finance_v26_verifier_bound_instrument_contract:tampered"
    with pytest.raises(ValidationError, match="frozen identities"):
        VerifierBoundInstrumentExecutionBinding.model_validate(binding_payload)

    checks = dict.fromkeys(NON_REPLAY_CHECK_IDS, False)
    values = {
        "execution_binding_id": EXPECTED_BINDING_ID,
        "job_id": "job:test",
        "task_package_id": "task:test",
        "checks": checks,
        "selected_evidence_ids": (),
        "operation_lineage_evidence_ids": (),
        "verification_support_ids": (),
        "cited_evidence_ids": (),
        "mechanism_event_ids": (),
        "normalized_answer": {},
        "matched_program_node_ids": (),
        "complete_solve_result": False,
    }
    provisional = OnlineNonReplayGateAudit.model_construct(audit_id="pending", **values)
    audit = OnlineNonReplayGateAudit(
        audit_id=online_non_replay_gate_audit_id(provisional),
        **values,
    )
    payload = audit.model_dump(mode="json")
    payload["checks"].pop("citation_complete")
    with pytest.raises(ValidationError, match="Gate vector is incomplete"):
        OnlineNonReplayGateAudit.model_validate(payload)


def test_raw_provider_artifact_rejects_prompt_mutation(prepared: Path) -> None:
    binding = VerifierBoundInstrumentExecutionBinding.model_validate_json(
        (prepared / "execution_binding.json").read_text(encoding="utf-8")
    )
    manifest = VerifierBoundInstrumentJobManifest.model_validate_json(
        (prepared / "frozen_job_manifest.json").read_text(encoding="utf-8")
    )
    prompt = "immutable prompt"
    telemetry = ModelCallTelemetry(
        provider="deepseek",
        endpoint_host="api.deepseek.com",
        model_requested="deepseek-v4-flash",
        model_selected="deepseek-v4-flash",
        request_hash=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        http_status=200,
        http_success=True,
        json_contract_success=True,
    )
    values = {
        "execution_binding_id": binding.binding_id,
        "job_id": manifest.jobs[0].job_id,
        "call_index": 0,
        "provider_call_id": ("finance_v26_verifier_bound_provider_call:" + "0" * 64),
        "prompt": prompt,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "response_payload": {"ok": True},
        "telemetry": telemetry,
    }
    from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_verifier_bound_instrument_requalification import (  # noqa: E501
        provider_call_id,
    )

    values["provider_call_id"] = provider_call_id(manifest.jobs[0].job_id, 0, telemetry)
    provisional = RawProviderCallArtifact.model_construct(artifact_id="pending", **values)
    artifact = RawProviderCallArtifact(
        artifact_id=raw_provider_call_artifact_id(provisional),
        **values,
    )
    payload = artifact.model_dump(mode="json")
    payload["prompt"] = "changed prompt"
    with pytest.raises(ValidationError, match="Prompt hash changed"):
        RawProviderCallArtifact.model_validate(payload)


def test_formal_v26_78_instrument_result_and_authorization() -> None:
    if not (FORMAL / "report.json").exists():
        pytest.skip("formal v26.78 online execution has not completed yet")
    report = VerifierBoundInstrumentRequalificationReport.model_validate_json(
        (FORMAL / "report.json").read_text(encoding="utf-8")
    )
    assert report.completed_rollout_count == report.expected_rollout_count == 32
    assert report.model_outcome_count == 32
    assert report.runtime_failure_count == report.instrument_failure_count == 0
    assert report.exact_requested_model_count == 32
    assert report.fallback_count == 0
    assert report.replay_pass_count == 32
    assert report.replay_failure_count == 0
    assert report.raw_integrity_audit.status == "passed"
    assert report.raw_integrity_audit.raw_before_scoring_pass_count == 32
    assert report.raw_integrity_audit.non_replay_gate_audit_pass_count == 32
    assert report.stop_ready_false_positive_count == 0
    assert report.stop_ready_false_negative_count == 0
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


def test_completed_run_replay_constructs_no_model_client(monkeypatch: pytest.MonkeyPatch) -> None:
    if not (FORMAL / "report.json").exists():
        pytest.skip("formal v26.78 online execution has not completed yet")
    report_before = (FORMAL / "report.json").read_bytes()

    def fail_client(_: AgentModelConfig) -> Any:
        raise AssertionError("completed-run replay constructed a model client")

    report = run_verifier_bound_instrument_requalification(
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
