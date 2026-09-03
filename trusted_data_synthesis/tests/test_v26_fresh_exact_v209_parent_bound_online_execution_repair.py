from __future__ import annotations

import hashlib
import json
import urllib.error
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_parent_bound_online_execution as prior,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_parent_bound_online_execution_repair as subject,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_parent_bound_online_execution_repair_models as models,
)
from trusted_synthesis.runtime.agent.client import LLMClientError

ROOT = Path(__file__).resolve().parents[2]


class FakeHttpResponse:
    status = 200

    def __enter__(self) -> FakeHttpResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(
            {
                "model": "deepseek-v4-flash",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": "{}", "reasoning_content": "x"},
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 2,
                    "total_tokens": 12,
                    "completion_tokens_details": {"reasoning_tokens": 1},
                },
            },
            separators=(",", ":"),
        ).encode("utf-8")


@pytest.fixture(scope="module")
def prepared() -> subject.PreparedReplacement:
    original = prior._git_identity  # noqa: SLF001
    prior._git_identity = lambda _root: ("1" * 40, "2" * 40)  # type: ignore[assignment]  # noqa: SLF001
    try:
        return subject.prepare_replacement(
            repository_root=ROOT,
            output_dir=ROOT / subject.OUTPUT_DIR,
        )
    finally:
        prior._git_identity = original  # type: ignore[assignment]  # noqa: SLF001


def test_independent_v224_failure_reconstruction() -> None:
    audit = subject._verify_v224(ROOT)  # noqa: SLF001
    assert audit.audit_id == (
        "finance_v26_225_postrun_repair_audit:"
        "7fc06cabbaccd9726741d7dd04725733b8b0991834aa5f2ff6a237f9c223ef42"
    )
    assert audit.request_intent_count == 192
    assert audit.failure_record_count == 192
    assert audit.stored_summary_zero_call_interpretation_valid is False


def test_conditional_replacement_authorization_is_fresh(
    prepared: subject.PreparedReplacement,
) -> None:
    assert prepared.authorization.authorization_id != prior.models.V223_AUTHORIZATION_ID
    assert prepared.authorization.exact_replacement_execution_authorized is True
    assert prepared.authorization.failed_job_recovery_authorized is False
    assert prepared.authorization.per_job_selective_rerun_authorized is False
    assert models.canonical_sha256(prepared.authorization.exact_job_ids) == (
        prior.models.EXACT_JOB_SET_SHA256
    )


def test_typed_dict_redacted_success_path(
    prepared: subject.PreparedReplacement,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(prepared.config.api_key_env, "synthetic-test-key")
    monkeypatch.setattr(prior.urllib.request, "urlopen", lambda *_a, **_k: FakeHttpResponse())
    client = prior.ExactRequestBodyDeepSeekClient(prepared.config)
    body = prior.v209._build_canonical_request_body(  # noqa: SLF001
        prepared.config,
        ({"role": "user", "content": "synthetic"},),
    )
    result = client.complete_body(body)
    assert result.public_value == {}
    assert isinstance(result.redacted_fields, dict)
    assert result.telemetry.http_success is True
    assert result.telemetry.total_tokens == 12


def test_typed_dict_redacted_error_path(
    prepared: subject.PreparedReplacement,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(prepared.config.api_key_env, "synthetic-test-key")

    def fail(*_args: object, **_kwargs: object) -> Any:
        raise urllib.error.URLError("synthetic transport failure")

    monkeypatch.setattr(prior.urllib.request, "urlopen", fail)
    client = prior.ExactRequestBodyDeepSeekClient(prepared.config)
    body = prior.v209._build_canonical_request_body(  # noqa: SLF001
        prepared.config,
        ({"role": "user", "content": "synthetic"},),
    )
    with pytest.raises(LLMClientError) as caught:
        client.complete_body(body)
    assert len(caught.value.telemetry) == 1
    assert caught.value.telemetry[0].http_success is False


def test_mock_http_response_drives_real_runner_and_closes_journal(
    prepared: subject.PreparedReplacement,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    isolated = replace(
        prepared,
        repository_root=tmp_path,
        output_dir=tmp_path / "replacement",
        ledger_path=tmp_path / "ledger" / "authorization.json",
    )
    isolated.output_dir.mkdir(parents=True)
    run_start = models.make_identity(
        models.RunStartReceipt,
        {
            "consumption_receipt_id": "synthetic-consumption",
            "preparation_id": prepared.preparation.preparation_id,
            "authorization_id": prepared.authorization.authorization_id,
            "execution_source_commit": "1" * 40,
            "execution_source_tree": "2" * 40,
            "started_at_utc": "2026-09-03T00:00:00Z",
        },
        field="receipt_id",
        prefix="finance_v26_226_replacement_run_start_receipt:",
    )
    monkeypatch.setenv(prepared.config.api_key_env, "synthetic-test-key")
    monkeypatch.setattr(prior.urllib.request, "urlopen", lambda *_a, **_k: FakeHttpResponse())
    client = prior.ExactRequestBodyDeepSeekClient(prepared.config)
    job = prepared.manifest.jobs[0]
    result = prior._execute_job(  # noqa: SLF001
        prepared=isolated,  # type: ignore[arg-type]
        run_start=run_start,  # type: ignore[arg-type]
        job=job,
        job_ordinal=0,
        client=client,
        record_model=models.JobExecutionRecord,
        failure_record_model=models.JobFailureRecord,
    )
    assert isinstance(result, models.JobExecutionRecord)
    assert result.terminal_kind == "first_response_abi_invalid"
    assert result.authorization_id == prepared.authorization.authorization_id
    assert len(result.provider_calls) == 1
    assert result.provider_calls[0].status == "succeeded"
    call_root = (
        isolated.output_dir
        / "provider_calls"
        / hashlib.sha256(job.job_id.encode("utf-8")).hexdigest()
    )
    assert len(list(call_root.glob("*.json"))) == 4
    assert all(
        (isolated.output_dir / descriptor.relative_path).is_file()
        for descriptor in (
            result.raw,
            result.result,
            result.trace,
            result.outcome,
            result.checkpoint,
        )
    )


def test_replacement_global_ledger_is_no_replace(
    prepared: subject.PreparedReplacement,
    tmp_path: Path,
) -> None:
    isolated = replace(
        prepared,
        repository_root=tmp_path,
        output_dir=tmp_path / "first",
        ledger_path=tmp_path / "ledger" / "authorization.json",
    )
    subject._consume(isolated)  # noqa: SLF001
    second = replace(isolated, output_dir=tmp_path / "second")
    with pytest.raises(FileExistsError):
        subject._consume(second)  # noqa: SLF001
    assert not second.output_dir.exists()


def test_repair_directive_hashes_are_exact() -> None:
    assert len(models.REPAIR_DIRECTIVE.encode("utf-8")) == 42
    assert hashlib.sha256(models.REPAIR_DIRECTIVE.encode()).hexdigest() == (
        models.REPAIR_DIRECTIVE_SHA256
    )
    assert len(models.CONDITIONAL_RUN_DIRECTIVE.encode("utf-8")) == 69
    assert hashlib.sha256(models.CONDITIONAL_RUN_DIRECTIVE.encode()).hexdigest() == (
        models.CONDITIONAL_RUN_DIRECTIVE_SHA256
    )
