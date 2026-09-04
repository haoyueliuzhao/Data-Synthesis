from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_parent_bound_online_execution as v224,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_online_execution as subject,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_unbound_provider_failure_recovery_online_execution_models as models,
)
from trusted_synthesis.runtime.agent.schema import ModelCallTelemetry

ROOT = Path(__file__).resolve().parents[2]
REVIEW = Path(
    "/home/zhuxinrui/.codex/attachments/9bb3c0ca-ae1d-47d2-8c2c-160c04c15823/pasted-text.txt"
)


@pytest.fixture(scope="module")
def prepared(tmp_path_factory: pytest.TempPathFactory) -> subject.PreparedRecoveryExecution:
    target = tmp_path_factory.mktemp("v26-233-prepare") / "online"
    original = subject.OUTPUT_DIR
    original_ledger = subject.LEDGER_DIR
    subject.OUTPUT_DIR = os.path.relpath(target, ROOT)
    subject.LEDGER_DIR = os.path.relpath(target.parent / "ledger", ROOT)
    try:
        value = subject.prepare_execution(
            repository_root=ROOT,
            output_dir=target,
            external_review_path=REVIEW,
        )
    finally:
        subject.OUTPUT_DIR = original
        subject.LEDGER_DIR = original_ledger
    assert not target.exists()
    return value


def _telemetry(request_sha256: str) -> ModelCallTelemetry:
    return ModelCallTelemetry(
        provider="deepseek",
        endpoint_host="api.deepseek.com",
        model_requested="deepseek-v4-flash",
        model_selected="deepseek-v4-flash",
        response_model="deepseek-v4-flash",
        request_hash=request_sha256,
        response_hash="1" * 64,
        http_status=200,
        http_success=True,
        json_contract_success=True,
        finish_reason="stop",
        response_content_length=32,
        reasoning_content_present=True,
        reasoning_content_length=64,
        reasoning_tokens=16,
        prompt_tokens=20,
        prompt_cache_hit_tokens=0,
        prompt_cache_miss_tokens=20,
        completion_tokens=12,
        total_tokens=32,
        estimated_cost=0.0001,
        cost_estimation_method="provider_cache_breakdown",
        latency_ms=1,
    )


class AbiInvalidClient:
    def complete_body(self, body: Any) -> v224.ProviderResponse:
        request_sha = models.canonical_sha256(dict(body))
        return v224.ProviderResponse(
            public_value={"answer": "not-an-action-payload"},
            telemetry=_telemetry(request_sha),
            redacted_fields={
                "model": "deepseek-v4-flash",
                "finish_reason": "stop",
                "reasoning_content_present": True,
                "reasoning_content_length": 64,
            },
        )


def test_prepare_closes_exact_guard_and_replay_without_writes(
    prepared: subject.PreparedRecoveryExecution,
) -> None:
    assert prepared.authorization.authorization_id == models.AUTHORIZATION_ID
    assert prepared.preparation.successful_prefix_projection_count == 55
    assert len(prepared.replay.rows) == len(prepared.recovery_population.jobs) == 33
    assert sum(len(item) for item in prepared.source.public_prefixes.values()) == 55
    assert prepared.config.max_output_tokens == 16_384
    assert prepared.preparation.provider_calls == prepared.preparation.credential_lookups == 0
    assert not prepared.output_dir.exists()
    assert not prepared.ledger_path.exists()


def test_exact_failed_request_is_first_live_call_after_local_prefix(
    prepared: subject.PreparedRecoveryExecution, tmp_path: Path
) -> None:
    isolated = replace(
        prepared,
        repository_root=tmp_path,
        output_dir=tmp_path / "recovery",
        ledger_path=tmp_path / "ledger.json",
    )
    isolated.output_dir.mkdir()
    run_start = models.make_identity(
        models.RecoveryRunStartReceipt,
        {
            "consumption_receipt_id": "synthetic-consumption",
            "preparation_id": prepared.preparation.preparation_id,
            "execution_source_id": "synthetic-source",
            "execution_source_commit": "1" * 40,
            "execution_source_tree": "2" * 40,
            "started_at_utc": "2026-09-04T00:00:00Z",
        },
        field="receipt_id",
        prefix=models.RecoveryRunStartReceipt.prefix(),
    )
    recovery_job = next(
        item for item in prepared.recovery_population.jobs if item.candidate.job_ordinal == 9
    )
    source_row = next(item for item in prepared.source.audit.source_rows if item.job_ordinal == 9)
    replay_row = next(item for item in prepared.replay.rows if item.job_ordinal == 9)
    historical_job = next(
        item
        for item in prepared.manifest.jobs
        if item.job_id == recovery_job.candidate.historical_job_id
    )
    result = subject._execute_job(  # noqa: SLF001
        prepared=isolated,
        run_start=run_start,
        recovery_job=recovery_job,
        historical_job=historical_job,
        source_row=source_row,
        replay_row=replay_row,
        public_prefix=prepared.source.public_prefixes[9],
        client=AbiInvalidClient(),
    )
    assert isinstance(result, models.RecoveryJobRecord)
    assert result.successful_prefix_projection_count == 2
    assert result.successful_prefix_provider_reissue_count == 0
    assert result.exact_failed_request_reissue_count == 1
    assert len(result.provider_calls) == 1
    assert result.provider_calls[0].request_sha256 == replay_row.failed_request_sha256
    assert result.terminal_kind == "first_response_abi_invalid"
    assert all((isolated.output_dir / item.relative_path).is_file() for item in result.layers)


def test_wrong_review_rejects_before_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad = tmp_path / "bad-review.txt"
    bad.write_bytes(REVIEW.read_bytes() + b"x")
    output = tmp_path / "online"
    monkeypatch.setattr(subject, "OUTPUT_DIR", os.path.relpath(output, ROOT))
    with pytest.raises(subject.V233Error, match="external.review"):
        subject.prepare_execution(repository_root=ROOT, output_dir=output, external_review_path=bad)
    assert not output.exists()


def test_consumption_ledger_is_no_replace(
    prepared: subject.PreparedRecoveryExecution, tmp_path: Path
) -> None:
    isolated = replace(
        prepared,
        repository_root=tmp_path,
        output_dir=tmp_path / "online",
        ledger_path=tmp_path / "ledger" / "authorization.json",
    )
    members = tuple(
        models.SourceMember(relative_path=path, sha256="1" * 64, byte_count=1)
        for path in subject.IMPLEMENTATION_PATHS
    )
    source = models.make_identity(
        models.ExecutionSourceIdentity,
        {
            "source_commit": "1" * 40,
            "source_tree": "2" * 40,
            "members": members,
            "member_set_sha256": models.canonical_sha256(
                tuple(item.model_dump(mode="json") for item in members)
            ),
        },
        field="source_id",
        prefix=models.ExecutionSourceIdentity.prefix(),
    )
    subject._consume(isolated, source)  # noqa: SLF001
    with pytest.raises(FileExistsError):
        subject._consume(isolated, source)  # noqa: SLF001
