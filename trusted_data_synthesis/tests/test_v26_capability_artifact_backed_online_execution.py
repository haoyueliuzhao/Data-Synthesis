from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.core.task.joint_presentation_receipt_hardening import (
    HardenedPublicPrompt,
)
from trusted_synthesis.core.task.state_local_presentation_hardening import (
    public_only_select_hardened_action,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_artifact_backed_online_execution as online,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import prospective_two_stage_stage1_client as stage_one
from trusted_synthesis.runtime.agent.prospective_semantic_action_response_grammar import (
    RESPONSE_PROTOCOL_VERSION,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig, ModelCallTelemetry

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
AUTHORIZATION = Path(
    "/home/zhuxinrui/.codex/attachments/5e903e35-c395-48fb-bf6a-7b4c19fe7b1d/pasted-text.txt"
)


class ScriptedOnlineClient:
    def __init__(self, config: AgentModelConfig, *, mode: str = "reference") -> None:
        self.config = config
        self.mode = mode
        self.semantic_calls = 0

    def complete_json_certified(
        self,
        prompt: str,
        certificate: Any,
    ) -> tuple[dict[str, Any], ModelCallTelemetry]:
        assert certificate == stage_one.certify_stage_one_request_pre_call(
            config=self.config,
            prompt=prompt,
            request_kind=certificate.request_kind,
            phase=certificate.phase,
        )
        if certificate.request_kind == "semantic_proposal":
            self.semantic_calls += 1
            outer = json.loads(prompt)
            public_prompt = HardenedPublicPrompt.model_validate(outer["public_prompt"])
            if self.mode == "malformed_action" and self.semantic_calls == 1:
                payload = {"state_id": public_prompt.state.state_token}
            else:
                action_id = public_only_select_hardened_action(public_prompt)
                if self.mode == "unknown_action" and self.semantic_calls == 1:
                    action_id = "0" * 24
                payload = {
                    "state_id": public_prompt.state.state_token,
                    "action_id": action_id,
                    "decision_kind": "execute_public_operation",
                    "protocol": RESPONSE_PROTOCOL_VERSION,
                }
        elif self.mode == "malformed_final":
            payload = {"answer": {"result": {"value": "0"}, "citations": []}}
        else:
            body = json.loads(prompt.split("\n", 1)[1])
            context = json.loads(body["public_context"])
            record = context["public_task"]["semantic_task"]["records"][0]
            payload = {
                "answer": {
                    "result": {"value": "0"},
                    "citations": [{"evidence_id": record["record_handle"]}],
                },
                "rationale_summary": "credential-free scripted fixture",
            }
        prompt_tokens = len(prompt.encode("utf-8"))
        completion_tokens = 64
        telemetry = ModelCallTelemetry(
            provider="deepseek",
            endpoint_host="api.deepseek.com",
            model_requested=stage_one.STAGE_ONE_MODEL_ID,
            model_selected=stage_one.STAGE_ONE_MODEL_ID,
            response_model=stage_one.STAGE_ONE_MODEL_ID,
            request_hash=stage_one._sha256_text(prompt),  # noqa: SLF001
            response_hash=canonical_hash(payload, prefix="v26_188_test_response:"),
            http_status=200,
            http_success=True,
            json_contract_success=True,
            finish_reason="stop",
            response_content_length=len(json.dumps(payload).encode("utf-8")),
            reasoning_content_present=True,
            reasoning_content_length=32,
            reasoning_tokens=16,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            estimated_cost=0,
            cost_estimation_method="conservative_cache_miss",
            latency_ms=0,
            fallback_used=False,
            discovery_attempted=False,
            discovered_model_count=0,
        )
        return payload, telemetry


@pytest.fixture(scope="module")
def prepared(tmp_path_factory: pytest.TempPathFactory) -> online.PreparedExecution:
    output = tmp_path_factory.mktemp("v26-188-prepared-parent") / "absent-run"
    return online.prepare_execution(package_root=PACKAGE_ROOT, output_dir=output)


@pytest.fixture(scope="module")
def config() -> AgentModelConfig:
    payload = json.loads((PACKAGE_ROOT / online.MODEL_PROFILE_PATH).read_text(encoding="utf-8"))
    return AgentModelConfig.model_validate(payload["model"])


def _run_one(
    prepared: online.PreparedExecution,
    config: AgentModelConfig,
    tmp_path: Path,
    *,
    mode: str,
) -> online.JobExecutionRecord:
    scoped = replace(prepared, output_dir=tmp_path / "run")
    return online.execute_job(
        prepared=scoped,
        job=scoped.frozen.manifest.jobs[0],
        client=ScriptedOnlineClient(config, mode=mode),
    )


def test_prepare_only_closes_exact_authority_without_output(
    prepared: online.PreparedExecution,
) -> None:
    assert prepared.preparation.exact_job_count == 192
    assert prepared.preparation.provider_calls == 0
    assert prepared.preparation.confirmation_payload_access_count == 0
    assert prepared.preparation.v186_contract_id == online.EXPECTED_V186_CONTRACT_ID
    assert not prepared.output_dir.exists()
    assert AUTHORIZATION.stat().st_size == online.AUTHORIZATION_BYTES
    assert online._sha256(AUTHORIZATION) == online.AUTHORIZATION_SHA256  # noqa: SLF001


def test_reference_job_persists_complete_artifact_backed_dag(
    prepared: online.PreparedExecution,
    config: AgentModelConfig,
    tmp_path: Path,
) -> None:
    record = _run_one(prepared, config, tmp_path, mode="reference")
    assert record.terminal_kind == "completed_qualified"
    assert record.provider_call_count == 2
    assert len(record.runtime_component_attempts) == 1
    assert record.bundle.row.first_policy_qualified_valid is True
    assert record.bundle.row.bounded_policy_qualified_valid is True
    assert len(record.provider_envelope_artifacts) == 2
    assert len(record.public_payload_projection_artifacts) == 2
    assert record.bundle.raw.artifact_byte_count > 0
    assert record.bundle.result.artifact_byte_count > 0


@pytest.mark.parametrize(
    ("mode", "terminal"),
    (
        ("malformed_action", "first_response_abi_invalid"),
        ("unknown_action", "first_action_reference_invalid"),
        ("malformed_final", "final_response_abi_invalid"),
    ),
)
def test_model_invalid_surfaces_remain_typed_denominator_rows(
    prepared: online.PreparedExecution,
    config: AgentModelConfig,
    tmp_path: Path,
    mode: str,
    terminal: str,
) -> None:
    record = _run_one(prepared, config, tmp_path, mode=mode)
    assert record.terminal_kind == terminal
    assert record.bundle.row.first_policy_qualified_valid is False
    assert record.bundle.row.bounded_policy_qualified_valid is False
    assert record.stage_two_provider_calls == 0
