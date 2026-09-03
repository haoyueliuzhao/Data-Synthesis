from __future__ import annotations

import hashlib
import os
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_parent_bound_online_execution as execution,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_parent_bound_online_execution_authorization as v223,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_parent_bound_online_execution_authorization_models as v223_models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_exact_v209_parent_bound_online_execution_models as models,
)
from trusted_synthesis.runtime.agent.schema import ModelCallTelemetry

ROOT = Path(__file__).resolve().parents[2]
ATTACHED_REVIEW = Path(
    "/home/zhuxinrui/.codex/attachments/e71df809-b233-44ba-8ad6-b4b0d481fa5f/pasted-text.txt"
)


def _review_path() -> Path:
    explicit = os.environ.get("V224_EXTERNAL_REVIEW")
    formal = ROOT / execution.OUTPUT_DIR / "external_review.txt"
    path = Path(explicit) if explicit else (formal if formal.is_file() else ATTACHED_REVIEW)
    if not path.is_file():
        pytest.skip("exact v26.224 external review is unavailable")
    return path


@pytest.fixture(scope="module")
def prepared(tmp_path_factory: pytest.TempPathFactory) -> execution.PreparedExecution:
    target = tmp_path_factory.mktemp("v26-224-prepare") / "online"
    original = execution.OUTPUT_DIR
    execution.OUTPUT_DIR = os.path.relpath(target, ROOT)
    try:
        value = execution.prepare_execution(
            repository_root=ROOT,
            output_dir=target,
            external_review_path=_review_path(),
        )
    finally:
        execution.OUTPUT_DIR = original
    assert not target.exists()
    return value


def _isolated(
    prepared: execution.PreparedExecution,
    root: Path,
    *,
    output_name: str,
    ledger_name: str = "authorization.json",
) -> execution.PreparedExecution:
    return replace(
        prepared,
        repository_root=root,
        output_dir=root / output_name,
        ledger_path=root / "global-ledger" / ledger_name,
    )


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


class AbiInvalidLiveClient:
    """Credential-free fake transport response for the real v26.209 Runner."""

    def complete_body(self, body: Any) -> execution.ProviderResponse:
        request_sha = models.canonical_sha256(dict(body))
        return execution.ProviderResponse(
            public_value={"answer": "not-an-action-payload"},
            telemetry=_telemetry(request_sha),
            redacted_fields={
                "model": "deepseek-v4-flash",
                "finish_reason": "stop",
                "reasoning_content_present": True,
                "reasoning_content_length": 64,
            },
        )


def _provider_call() -> models.ProviderCallDescriptor:
    run_start = "run-start"
    job_id = "job"
    request_sha = "1" * 64
    intention_sha = "2" * 64
    provider_call_id = models.provider_call_identity(
        run_start_receipt_id=run_start,
        job_id=job_id,
        call_ordinal=0,
        request_sha256=request_sha,
        intention_sha256=intention_sha,
    )
    projection = {"answer": {"value": "public-only"}}
    payload = models.canonical_bytes(projection) + b"\n"
    artifact = models.make_identity(
        models.ProviderCallArtifact,
        {
            "provider_call_id": provider_call_id,
            "artifact_kind": "response_metadata",
            "relative_path": "provider_calls/job/call_00_response_metadata.json",
            "sha256": hashlib.sha256(payload).hexdigest(),
            "byte_count": len(payload),
            "public_projection": projection,
            "public_projection_sha256": models.canonical_sha256(projection),
            "public_projection_present": True,
        },
        field="artifact_id",
        prefix="finance_v26_224_redacted_provider_call_artifact:",
    )
    return models.make_identity(
        models.ProviderCallDescriptor,
        {
            "provider_call_id": provider_call_id,
            "run_start_receipt_id": run_start,
            "job_id": job_id,
            "call_ordinal": 0,
            "intention_sha256": intention_sha,
            "status": "succeeded",
            "request_sha256": request_sha,
            "response_sha256": models.canonical_sha256(projection),
            "input_tokens": 20,
            "output_tokens": 12,
            "artifacts": (artifact,),
        },
        field="descriptor_id",
        prefix="finance_v26_224_redacted_provider_call_descriptor:",
    )


def _job_record(
    prepared: execution.PreparedExecution,
    *,
    ordinal: int,
    run_start_receipt_id: str = "run-start",
) -> models.JobExecutionRecord:
    job_id = prepared.authorization.exact_job_ids[ordinal]
    job = {item.job_id: item for item in prepared.manifest.jobs}[job_id]
    safe = hashlib.sha256(job_id.encode()).hexdigest()
    terminal = "completed_invalid"
    raw = models.make_identity(
        models.RawExecutionDescriptor,
        {
            "run_start_receipt_id": run_start_receipt_id,
            "job_id": job_id,
            "namespace_id": job.raw_namespace,
            "relative_path": f"evidence/raw/{safe}.json",
            "terminal_kind": terminal,
            "terminal_source": "current_state_runner_observation",
            "provider_call_descriptor_ids": (),
            "payload_sha256": "1" * 64,
            "payload_byte_count": 1,
            "persisted_sequence": 0,
        },
        field="descriptor_id",
        prefix="finance_v26_224_empirical_raw_descriptor:",
    )
    result = models.make_identity(
        models.ResultDescriptor,
        {
            "run_start_receipt_id": run_start_receipt_id,
            "job_id": job_id,
            "namespace_id": job.result_namespace,
            "relative_path": f"evidence/result/{safe}.json",
            "terminal_kind": terminal,
            "raw_descriptor_id": raw.descriptor_id,
            "raw_namespace_id": raw.namespace_id,
            "raw_persisted_sequence": raw.persisted_sequence,
            "payload_sha256": "2" * 64,
            "payload_byte_count": 1,
            "persisted_sequence": 1,
        },
        field="descriptor_id",
        prefix="finance_v26_224_empirical_result_descriptor:",
    )
    trace = models.make_identity(
        models.TraceDescriptor,
        {
            "run_start_receipt_id": run_start_receipt_id,
            "job_id": job_id,
            "namespace_id": job.trace_namespace,
            "relative_path": f"evidence/trace/{safe}.json",
            "terminal_kind": terminal,
            "raw_descriptor_id": raw.descriptor_id,
            "raw_namespace_id": raw.namespace_id,
            "result_descriptor_id": result.descriptor_id,
            "result_namespace_id": result.namespace_id,
            "result_persisted_sequence": result.persisted_sequence,
            "provider_call_descriptor_ids": (),
            "payload_sha256": "3" * 64,
            "payload_byte_count": 1,
            "persisted_sequence": 2,
        },
        field="descriptor_id",
        prefix="finance_v26_224_empirical_trace_descriptor:",
    )
    outcome = models.make_identity(
        models.OutcomeDescriptor,
        {
            "run_start_receipt_id": run_start_receipt_id,
            "job_id": job_id,
            "namespace_id": job.outcome_namespace,
            "relative_path": f"evidence/outcome/{safe}.json",
            "terminal_kind": terminal,
            "trace_descriptor_id": trace.descriptor_id,
            "trace_namespace_id": trace.namespace_id,
            "trace_persisted_sequence": trace.persisted_sequence,
            "payload_sha256": "4" * 64,
            "payload_byte_count": 1,
            "persisted_sequence": 3,
        },
        field="descriptor_id",
        prefix="finance_v26_224_empirical_outcome_descriptor:",
    )
    checkpoint = models.make_identity(
        models.CheckpointDescriptor,
        {
            "run_start_receipt_id": run_start_receipt_id,
            "job_id": job_id,
            "job_ordinal": ordinal,
            "relative_path": f"checkpoints/job_{ordinal:03d}.json",
            "terminal_kind": terminal,
            "outcome_descriptor_id": outcome.descriptor_id,
            "outcome_namespace_id": outcome.namespace_id,
            "outcome_persisted_sequence": outcome.persisted_sequence,
            "payload_sha256": "5" * 64,
            "payload_byte_count": 1,
            "persisted_sequence": 4,
        },
        field="descriptor_id",
        prefix="finance_v26_224_empirical_checkpoint_descriptor:",
    )
    return models.make_identity(
        models.JobExecutionRecord,
        {
            "run_start_receipt_id": run_start_receipt_id,
            "authorization_id": prepared.authorization.authorization_id,
            "job_id": job_id,
            "job_ordinal": ordinal,
            "terminal_kind": terminal,
            "terminal_source": "current_state_runner_observation",
            "provider_calls": (),
            "raw": raw,
            "result": result,
            "trace": trace,
            "outcome": outcome,
            "checkpoint": checkpoint,
        },
        field="record_id",
        prefix="finance_v26_224_online_job_execution_record:",
    )


@pytest.fixture(scope="module")
def job_records(prepared: execution.PreparedExecution) -> tuple[models.JobExecutionRecord, ...]:
    return tuple(_job_record(prepared, ordinal=index) for index in range(192))


def _summary(
    prepared: execution.PreparedExecution,
    *,
    records: tuple[models.JobExecutionRecord, ...],
    failures: tuple[models.JobFailureRecord, ...],
    status: str,
) -> models.ExecutionSummary:
    terminals = {kind: 0 for kind in models.TERMINAL_KINDS}
    for record in records:
        terminals[record.terminal_kind] += 1
    failure_partition = {"unbound_provider_failure": 0, "host_failure": 0}
    for failure in failures:
        failure_partition[failure.failure_kind] += 1
    return models.make_identity(
        models.ExecutionSummary,
        {
            "preparation_id": prepared.preparation.preparation_id,
            "consumption_receipt_id": "consumption",
            "run_start_receipt_id": "run-start",
            "authorization_id": prepared.authorization.authorization_id,
            "execution_status": status,
            "records": records,
            "failure_records": failures,
            "exact_job_set_sha256": prepared.authorization.exact_job_set_sha256,
            "completed_job_record_count": len(records),
            "failure_record_count": len(failures),
            "raw_count": len(records),
            "result_count": len(records),
            "trace_count": len(records),
            "outcome_count": len(records),
            "checkpoint_count": len(records),
            "terminal_partition": terminals,
            "failure_partition": failure_partition,
            "provider_call_count": 0,
            "input_tokens": 0,
            "output_tokens": 0,
        },
        field="summary_id",
        prefix="finance_v26_224_execution_summary:",
    )


def test_prepare_exact_review_freeze_guard_is_zero_write(
    prepared: execution.PreparedExecution,
) -> None:
    assert prepared.external_authorization.review_sha256 == execution.EXTERNAL_REVIEW_SHA256
    assert prepared.v223_freeze.artifact_manifest_id == models.V223_MANIFEST_ID
    assert prepared.v223_freeze.artifact_root == models.V223_ARTIFACT_ROOT
    assert prepared.authorization.authorization_id == models.V223_AUTHORIZATION_ID
    assert prepared.admission.authorization_id == prepared.authorization.authorization_id
    assert prepared.admission.diagnostic_nonconsuming_probe
    assert not prepared.admission.authorization_consumed
    assert prepared.preparation.authorization_consumed is False
    assert prepared.preparation.provider_calls == prepared.preparation.credential_lookups == 0
    assert not prepared.output_dir.exists()


def test_wrong_external_review_rejects_before_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad_review = tmp_path / "wrong-review.txt"
    bad_review.write_bytes(_review_path().read_bytes() + b"changed")
    output = tmp_path / "online"
    monkeypatch.setattr(execution, "OUTPUT_DIR", os.path.relpath(output, ROOT))
    with pytest.raises(execution.V224Error, match="external audit bytes differ"):
        execution.prepare_execution(
            repository_root=ROOT,
            output_dir=output,
            external_review_path=bad_review,
        )
    assert not output.exists()


def test_authorization_file_is_canonical_newline_but_guard_consumes_canonical(
    prepared: execution.PreparedExecution,
) -> None:
    assert prepared.authorization_file_bytes == prepared.authorization_canonical_bytes + b"\n"
    assert hashlib.sha256(prepared.authorization_file_bytes).hexdigest() == (
        models.V223_AUTHORIZATION_SHA256
    )
    guard = v223_models.PrecredentialAuthorizationGuard(
        expected_authorization=prepared.authorization,
        expected_authorization_bytes=prepared.authorization_canonical_bytes,
    )
    assert guard.admit(**v223._request(prepared.authorization)) == prepared.admission  # noqa: SLF001
    with pytest.raises(ValueError, match="authorization bytes differ"):
        v223_models.PrecredentialAuthorizationGuard(
            expected_authorization=prepared.authorization,
            expected_authorization_bytes=prepared.authorization_file_bytes,
        )


def test_global_ledger_rejects_second_consumption_before_second_output(
    prepared: execution.PreparedExecution, tmp_path: Path
) -> None:
    first = _isolated(prepared, tmp_path, output_name="first")
    consumption, run_start = execution._consume_authorization(  # noqa: SLF001
        prepared=first,
        source_identity=("1" * 40, "2" * 40),
    )
    assert first.ledger_path.read_bytes() == execution._encoded(consumption)  # noqa: SLF001
    assert (first.output_dir / "run_start_receipt.json").read_bytes() == (
        execution._encoded(run_start)  # noqa: SLF001
    )
    second = _isolated(prepared, tmp_path, output_name="second")
    with pytest.raises(FileExistsError):
        execution._consume_authorization(  # noqa: SLF001
            prepared=second,
            source_identity=("3" * 40, "4" * 40),
        )
    assert not second.output_dir.exists()


def test_durable_receipts_exist_before_credential_and_client_construction(
    prepared: execution.PreparedExecution,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    isolated = _isolated(prepared, tmp_path, output_name="ordered")
    events: list[str] = []
    original_consume = execution._consume_authorization  # noqa: SLF001

    def consume(**kwargs: Any) -> Any:
        result = original_consume(**kwargs)
        events.append("receipts")
        return result

    def credential(_root: Path, _key: str) -> None:
        assert isolated.ledger_path.is_file()
        assert (isolated.output_dir / "authorization_consumption_receipt.json").is_file()
        assert (isolated.output_dir / "run_start_receipt.json").is_file()
        events.append("credential")

    class StopBeforeJobs(RuntimeError):
        pass

    def client_factory(_config: Any) -> Any:
        events.append("client")
        raise StopBeforeJobs

    monkeypatch.setattr(execution, "_git_identity", lambda _root: ("5" * 40, "6" * 40))
    monkeypatch.setattr(execution, "_consume_authorization", consume)
    monkeypatch.setattr(execution, "_load_env_key", credential)
    with pytest.raises(StopBeforeJobs):
        execution.execute(prepared=isolated, workers=1, client_factory=client_factory)
    assert events == ["receipts", "credential", "client"]


def test_provider_call_models_enforce_redaction_path_and_identity() -> None:
    descriptor = _provider_call()
    artifact = descriptor.artifacts[0]
    assert descriptor.redacted and not descriptor.raw_request_present
    assert not descriptor.raw_response_present and not descriptor.private_reasoning_present
    assert artifact.redacted and not artifact.prompt_content_present
    assert not artifact.raw_provider_response_present and not artifact.credential_content_present
    assert artifact.public_projection_sha256 == models.canonical_sha256(artifact.public_projection)
    invalid = artifact.model_dump(mode="python", warnings=False)
    invalid["relative_path"] = "../escape.json"
    with pytest.raises(ValueError):
        models.ProviderCallArtifact.model_validate(invalid)
    invalid = artifact.model_dump(mode="python", warnings=False)
    invalid["private_reasoning_present"] = True
    with pytest.raises(ValueError):
        models.ProviderCallArtifact.model_validate(invalid)


@pytest.mark.parametrize("terminal_kind", models.TERMINAL_KINDS)
def test_terminal_source_partition_accepts_exact_source_and_rejects_crossed_source(
    terminal_kind: models.TerminalKind,
) -> None:
    source: models.TerminalSource = (
        "v26_218_source_bound_failure"
        if terminal_kind in models.FAILURE_TERMINAL_KINDS
        else "current_state_runner_observation"
    )
    values = {
        "run_start_receipt_id": "run-start",
        "job_id": "job",
        "namespace_id": "raw-namespace",
        "relative_path": "evidence/raw/job.json",
        "terminal_kind": terminal_kind,
        "terminal_source": source,
        "provider_call_descriptor_ids": (),
        "payload_sha256": "7" * 64,
        "payload_byte_count": 1,
        "persisted_sequence": 0,
    }
    descriptor = models.make_identity(
        models.RawExecutionDescriptor,
        values,
        field="descriptor_id",
        prefix="finance_v26_224_empirical_raw_descriptor:",
    )
    assert descriptor.terminal_source == source
    values["terminal_source"] = (
        "current_state_runner_observation"
        if source == "v26_218_source_bound_failure"
        else "v26_218_source_bound_failure"
    )
    with pytest.raises(ValueError, match="Raw descriptor differs"):
        models.make_identity(
            models.RawExecutionDescriptor,
            values,
            field="descriptor_id",
            prefix="finance_v26_224_empirical_raw_descriptor:",
        )


def test_execution_summary_strictly_separates_complete_and_incomplete(
    prepared: execution.PreparedExecution,
    job_records: tuple[models.JobExecutionRecord, ...],
) -> None:
    complete = _summary(prepared, records=job_records, failures=(), status="completed")
    assert complete.execution_status == "completed"
    assert complete.completed_job_record_count == complete.checkpoint_count == 192
    failed_job_id = prepared.authorization.exact_job_ids[-1]
    failure = models.make_identity(
        models.JobFailureRecord,
        {
            "run_start_receipt_id": "run-start",
            "authorization_id": prepared.authorization.authorization_id,
            "job_id": failed_job_id,
            "job_ordinal": 191,
            "failure_kind": "host_failure",
            "error_sha256": "8" * 64,
            "provider_calls": (),
        },
        field="record_id",
        prefix="finance_v26_224_job_failure_record:",
    )
    incomplete = _summary(
        prepared,
        records=job_records[:-1],
        failures=(failure,),
        status="incomplete",
    )
    assert incomplete.execution_status == "incomplete"
    assert incomplete.failure_partition["host_failure"] == 1
    with pytest.raises(ValueError, match="execution Summary differs"):
        _summary(prepared, records=job_records, failures=(), status="incomplete")
    with pytest.raises(ValueError, match="execution Summary differs"):
        _summary(
            prepared,
            records=job_records[:-1],
            failures=(failure,),
            status="completed",
        )


def test_fake_client_drives_real_v209_runner_and_five_layer_persistence(
    prepared: execution.PreparedExecution, tmp_path: Path
) -> None:
    isolated = _isolated(prepared, tmp_path, output_name="single-job")
    _consumption, run_start = execution._consume_authorization(  # noqa: SLF001
        prepared=isolated,
        source_identity=("9" * 40, "a" * 40),
    )
    job_id = isolated.authorization.exact_job_ids[0]
    job = {item.job_id: item for item in isolated.manifest.jobs}[job_id]
    record = execution._execute_job(  # noqa: SLF001
        prepared=isolated,
        run_start=run_start,
        job=job,
        job_ordinal=0,
        client=AbiInvalidLiveClient(),  # type: ignore[arg-type]
    )
    assert isinstance(record, models.JobExecutionRecord)
    assert record.terminal_kind == "first_response_abi_invalid"
    assert record.terminal_source == "current_state_runner_observation"
    assert len(record.provider_calls) == 1
    assert tuple(
        item.persisted_sequence
        for item in (record.raw, record.result, record.trace, record.outcome, record.checkpoint)
    ) == (0, 1, 2, 3, 4)
    for descriptor in (
        record.raw,
        record.result,
        record.trace,
        record.outcome,
        record.checkpoint,
    ):
        path = isolated.output_dir / descriptor.relative_path
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == descriptor.payload_sha256
        assert path.stat().st_size == descriptor.payload_byte_count


def test_artifact_manifest_helper_is_sorted_self_excluding_and_path_bound(
    tmp_path: Path,
) -> None:
    root = tmp_path / "artifacts"
    execution._durable_write_no_replace(root / "z.json", b"z\n")  # noqa: SLF001
    execution._durable_write_no_replace(root / "nested" / "a.json", b"a\n")  # noqa: SLF001
    execution._durable_write_no_replace(  # noqa: SLF001
        root / "execution_artifact_manifest.json", b"old seal\n"
    )
    manifest = execution._artifact_manifest(root)  # noqa: SLF001
    assert tuple(item.relative_path for item in manifest.members) == (
        "nested/a.json",
        "z.json",
    )
    assert manifest.file_count == 2
    assert manifest.total_byte_count == 4
    rebuilt = models.artifact_manifest(
        execution.RUN_ID,
        {"z.json": b"z\n", "nested/a.json": b"a\n"},
    )
    assert rebuilt == manifest
