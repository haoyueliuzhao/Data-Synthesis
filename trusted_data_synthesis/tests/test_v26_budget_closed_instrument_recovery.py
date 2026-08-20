from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_closed_instrument_recovery import (  # noqa: E501
    FAILED_CHECKPOINT_COUNT,
    FAILED_ESTIMATED_COST_USD,
    FAILED_EXPOSED_JOB_COUNT,
    FAILED_PROVIDER_CALL_COUNT,
    FAILED_PROVIDER_TOTAL_TOKENS,
    UNOPENED_CONTINUATION_JOB_COUNT,
    BudgetRecoveryPreflightReport,
    BudgetRecoveryRawExecution,
    _reconstruct_exposed_raw,
    build_budget_recovery_preflight,
    run_budget_closed_instrument_recovery,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig, ModelCallTelemetry

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts/vtdo_experiment"
FAILED = (
    ARTIFACTS / "finance_v26_84_budget_closed_verifier_bound_instrument_requalification_20260820"
)
TASK_SOURCE = (
    ARTIFACTS / "finance_v26_82_budget_closed_verifier_bound_instrument_population_v2_20260820"
)
VERIFIER = ARTIFACTS / "finance_v26_75_authority_preserving_verifier_qualification_v2_20260819"
PREFLIGHT = (
    ARTIFACTS / "finance_v26_83_budget_closed_verifier_bound_instrument_preflight_v2_20260820"
)
RECOVERY_RUN_ID = "finance_v26_86_budget_closed_verifier_bound_instrument_recovery_20260820"
PREFLIGHT_FILES = (
    "failed_run_audit.json",
    "failed_run_job_audits.json",
    "raw_provider_artifact_manifest.json",
    "recovery_source_replay_audit.json",
    "recovery_contract.json",
    "recovery_manifest.json",
    "recovery_execution_binding.json",
    "report.json",
)


def _prepare(output: Path) -> Any:
    return build_budget_recovery_preflight(
        recovery_run_id=RECOVERY_RUN_ID,
        failed_run_dir=FAILED,
        task_source_dir=TASK_SOURCE,
        verifier_qualification_dir=VERIFIER,
        preflight_dir=PREFLIGHT,
        output_dir=output,
        package_root=ROOT,
    )


def test_failed_run_replay_and_job_partition_are_exact(tmp_path: Path) -> None:
    prepared = _prepare(tmp_path / "preflight")
    audit = prepared.failed_run_audit
    assert audit.exposed_job_count == FAILED_EXPOSED_JOB_COUNT
    assert audit.unopened_job_count == UNOPENED_CONTINUATION_JOB_COUNT
    assert audit.raw_provider_call_artifact_count == FAILED_PROVIDER_CALL_COUNT
    assert audit.provider_total_tokens == FAILED_PROVIDER_TOTAL_TOKENS
    assert audit.estimated_cost_usd == FAILED_ESTIMATED_COST_USD
    assert audit.raw_execution_artifact_count == 4
    assert audit.rollout_checkpoint_count == FAILED_CHECKPOINT_COUNT == 3
    assert audit.model_contract_failure_replay_count == 4
    assert audit.budget_exhausted_no_call_replay_count == 16
    assert audit.completed_trajectory_replay_count == 0
    assert audit.recovered_observation_count == 128
    assert audit.post_terminal_short_circuit_prompt_count == 16
    assert all(item.zero_generation_replay_passed for item in audit.job_audits)
    assert set(audit.exposed_job_ids).isdisjoint(audit.unopened_job_ids)
    assert len(set(audit.exposed_job_ids) | set(audit.unopened_job_ids)) == 32


def test_recovery_preflight_dual_build_is_byte_identical(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    prepared = _prepare(first)
    rebuilt = _prepare(second)
    assert prepared.preflight == rebuilt.preflight
    assert prepared.preflight.model_api_calls == 0
    assert not prepared.preflight.model_client_constructed
    assert prepared.preflight.exposed_job_zero_generation_replay_count == 20
    assert prepared.preflight.unopened_job_count == 12
    assert all(
        (first / name).read_bytes() == (second / name).read_bytes() for name in PREFLIGHT_FILES
    )


def test_post_terminal_short_circuit_suffix_is_schema_bound(tmp_path: Path) -> None:
    prepared = _prepare(tmp_path / "preflight")
    recovery_job = next(
        item
        for item in prepared.recovery_manifest.jobs
        if item.recovery_role == "zero_generation_replay"
        and next(
            audit
            for audit in prepared.failed_run_audit.job_audits
            if audit.job_id == item.original_job.job_id
        ).post_terminal_short_circuit_prompt_count
        == 1
    )
    job = recovery_job.original_job
    records = {item.record_id: item for item in prepared.records}
    environments = {item.manifest_id: item for item in prepared.environments}
    raw = _reconstruct_exposed_raw(
        recovery_job=recovery_job,
        prepared=prepared,
        failed_run_dir=FAILED,
        record=records[job.task_record_id],
        environment=environments[job.environment_manifest_id],
        output_dir=tmp_path / "recovered",
    )
    assert len(raw.provider_call_ids) + 1 == len(raw.provider_budget_audit.certificates)
    assert len(raw.attempted_model_prompts) == len(raw.provider_budget_audit.certificates) + 1
    assert raw.post_terminal_short_circuit_prompts == raw.attempted_model_prompts[-1:]
    payload = raw.model_dump(mode="json")
    payload["post_terminal_short_circuit_prompts"] = []
    with pytest.raises(ValidationError, match="post-terminal short-circuit Prompt suffix changed"):
        BudgetRecoveryRawExecution.model_validate(payload)


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


def test_fixture_recovery_completes_and_replays_without_client(tmp_path: Path) -> None:
    clients: list[_FixtureProviderClient] = []

    def client_factory(config: AgentModelConfig) -> Any:
        client = _FixtureProviderClient(config)
        clients.append(client)
        return client

    recovery_preflight = tmp_path / "preflight"
    output = tmp_path / "recovery"
    report = run_budget_closed_instrument_recovery(
        recovery_run_id=RECOVERY_RUN_ID,
        failed_run_dir=FAILED,
        task_source_dir=TASK_SOURCE,
        verifier_qualification_dir=VERIFIER,
        preflight_dir=PREFLIGHT,
        recovery_preflight_output_dir=recovery_preflight,
        output_dir=output,
        package_root=ROOT,
        workers=4,
        client_factory=client_factory,
    )
    assert report.completed_rollout_count == 32
    assert report.zero_generation_replayed_job_count == 20
    assert report.continuation_model_job_count == 12
    assert report.exposed_job_model_call_count == 0
    assert report.raw_lineage_audit.status == "passed"
    assert report.raw_lineage_audit.original_provider_exact_byte_pass_count == 152
    assert len(clients) == 1 and clients[0].call_count > 0
    report_bytes = (output / "report.json").read_bytes()

    def fail_client(_: AgentModelConfig) -> Any:
        raise AssertionError("completed Recovery replay constructed a model client")

    replayed = run_budget_closed_instrument_recovery(
        recovery_run_id=RECOVERY_RUN_ID,
        failed_run_dir=FAILED,
        task_source_dir=TASK_SOURCE,
        verifier_qualification_dir=VERIFIER,
        preflight_dir=PREFLIGHT,
        recovery_preflight_output_dir=recovery_preflight,
        output_dir=output,
        package_root=ROOT,
        workers=4,
        client_factory=fail_client,
    )
    assert replayed.report_id == report.report_id
    assert (output / "report.json").read_bytes() == report_bytes
    assert len((output / "recovery_rollouts.checkpoint.jsonl").read_text().splitlines()) == 32


def test_formal_recovery_preflight_when_present() -> None:
    path = ARTIFACTS / "finance_v26_85_budget_closed_recovery_preflight_20260820" / "report.json"
    if not path.exists():
        pytest.skip("formal v26.85 preflight has not been materialized")
    report = BudgetRecoveryPreflightReport.model_validate_json(path.read_text(encoding="utf-8"))
    assert report.status == "passed"
    assert report.model_api_calls == 0
    assert report.exposed_job_zero_generation_replay_count == 20
    assert report.unopened_job_count == 12
