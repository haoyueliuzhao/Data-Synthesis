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
def preflight_objects() -> subject.RepairPreflightObjects:
    members = tuple(
        models.SourceMember(
            relative_path=path,
            sha256=hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
            byte_count=len((ROOT / path).read_bytes()),
        )
        for path in sorted(subject.IMPLEMENTATION_PATHS)
    )
    source = models.make_identity(
        models.RepairPreflightSourceIdentity,
        {
            "source_commit": "1" * 40,
            "source_tree": "2" * 40,
            "implementation_members": members,
            "implementation_member_set_sha256": models.canonical_sha256(
                tuple(item.model_dump(mode="json", warnings=False) for item in members)
            ),
        },
        field="source_id",
        prefix="finance_v26_225_repair_source_identity:",
    )
    return subject._construct_preflight_objects(  # noqa: SLF001
        repository_root=ROOT,
        runtime_output_dir=ROOT / subject.OUTPUT_DIR,
        source_identity=source,
    )


@pytest.fixture(scope="module")
def prepared(
    preflight_objects: subject.RepairPreflightObjects,
) -> subject.PreparedReplacement:
    objects = preflight_objects
    loaded = objects.loaded
    authorization = objects.authorization
    return subject.PreparedReplacement(
        repository_root=ROOT,
        package_root=ROOT / "trusted_data_synthesis",
        output_dir=ROOT / subject.OUTPUT_DIR,
        ledger_path=(
            ROOT
            / subject.LEDGER_DIR
            / f"{hashlib.sha256(authorization.authorization_id.encode()).hexdigest()}.json"
        ),
        postrun_audit=objects.postrun_audit,
        repair_control_audit=objects.repair_control_audit,
        authorization=authorization,
        authorization_bytes=objects.authorization_bytes,
        preparation=objects.preparation,
        catalog=loaded["catalog"],
        manifest=loaded["manifest"],
        implementation=loaded["implementation"],
        frozen_parents=loaded["parents"],
        runtime=loaded["runtime"],
        config=loaded["config"],
        bindings=loaded["bindings"],
    )


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
    assert (
        prepared.preparation.repair_control_audit_id
        == prepared.repair_control_audit.audit_id
        == prepared.authorization.repair_control_audit_id
    )
    assert prepared.repair_control_audit.success_mock_http_calls == 1
    assert prepared.repair_control_audit.error_mock_http_calls == 1
    assert prepared.repair_control_audit.success_journal_files == 4
    assert prepared.repair_control_audit.error_journal_files == 4
    assert prepared.repair_control_audit.success_five_layer_files == 5
    assert prepared.repair_control_audit.real_provider_calls == 0
    assert (
        prepared.preparation.authorization_sha256
        == hashlib.sha256(prepared.authorization_bytes).hexdigest()
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
        record_identity_prefix="finance_v26_226_replacement_job_record:",
        failure_identity_prefix="finance_v26_226_replacement_job_failure:",
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
    projection = subject._provider_relation_projection(  # noqa: SLF001
        output_dir=isolated.output_dir,
        authorization_id=prepared.authorization.authorization_id,
        run_start_receipt_id=run_start.receipt_id,
    )
    assert projection["relation_closed"] is True
    descriptor_path = next((isolated.output_dir / "provider_calls").rglob("*_descriptor.json"))
    descriptor_path.unlink()
    orphaned = subject._provider_relation_projection(  # noqa: SLF001
        output_dir=isolated.output_dir,
        authorization_id=prepared.authorization.authorization_id,
        run_start_receipt_id=run_start.receipt_id,
    )
    assert orphaned["relation_closed"] is False
    assert orphaned["orphan_request_intent_count"] == 1


def test_replacement_global_ledger_is_no_replace(
    prepared: subject.PreparedReplacement,
    preflight_objects: subject.RepairPreflightObjects,
    tmp_path: Path,
) -> None:
    formal_authorization = (
        tmp_path / subject.PREFLIGHT_DIR / "conditional_replacement_authorization.json"
    )
    formal_authorization.parent.mkdir(parents=True)
    formal_authorization.write_bytes(prepared.authorization_bytes)
    isolated = replace(
        prepared,
        repository_root=tmp_path,
        package_root=tmp_path / "trusted_data_synthesis",
        output_dir=tmp_path / subject.OUTPUT_DIR,
        ledger_path=(
            tmp_path
            / subject.LEDGER_DIR
            / f"{hashlib.sha256(prepared.authorization.authorization_id.encode()).hexdigest()}.json"
        ),
    )
    subject._consume(isolated, refreshed=preflight_objects)  # noqa: SLF001
    with pytest.raises(FileExistsError):
        subject._consume(isolated, refreshed=preflight_objects)  # noqa: SLF001
    assert isolated.output_dir.is_dir()


def test_refreshed_execution_parent_substitution_rejects_before_ledger(
    prepared: subject.PreparedReplacement,
    preflight_objects: subject.RepairPreflightObjects,
) -> None:
    changed_config = prepared.config.model_copy(update={"timeout_seconds": 999.0})
    forged = replace(prepared, config=changed_config)
    with pytest.raises(ValueError, match="refreshed execution parent"):
        subject._admit_refreshed_prepared(forged, preflight_objects)  # noqa: SLF001
    changed_manifest = prepared.manifest.model_copy(
        update={"jobs": tuple(reversed(prepared.manifest.jobs))}
    )
    with pytest.raises(ValueError, match="refreshed execution parent"):
        subject._admit_refreshed_prepared(  # noqa: SLF001
            replace(prepared, manifest=changed_manifest), preflight_objects
        )
    with pytest.raises(ValueError, match="refreshed execution parent"):
        subject._admit_refreshed_prepared(  # noqa: SLF001
            replace(prepared, output_dir=prepared.output_dir.parent / "forged"),
            preflight_objects,
        )


def test_fully_rehashed_authorization_rejects_before_ledger(
    prepared: subject.PreparedReplacement,
    preflight_objects: subject.RepairPreflightObjects,
    tmp_path: Path,
) -> None:
    formal_authorization = (
        tmp_path / subject.PREFLIGHT_DIR / "conditional_replacement_authorization.json"
    )
    formal_authorization.parent.mkdir(parents=True)
    formal_authorization.write_bytes(prepared.authorization_bytes)
    values = prepared.authorization.model_dump(
        mode="json", exclude={"authorization_id"}, warnings=False
    )
    values["repaired_source_commit"] = "f" * 40
    forged_authorization = models.make_identity(
        models.ConditionalReplacementAuthorization,
        values,
        field="authorization_id",
        prefix="finance_v26_225_repaired_replacement_execution_authorization:",
    )
    forged_bytes = subject._encoded(forged_authorization)  # noqa: SLF001
    preparation_values = prepared.preparation.model_dump(
        mode="json", exclude={"preparation_id"}, warnings=False
    )
    preparation_values.update(
        {
            "authorization_id": forged_authorization.authorization_id,
            "authorization_sha256": hashlib.sha256(forged_bytes).hexdigest(),
            "repaired_source_commit": "f" * 40,
        }
    )
    forged_preparation = models.make_identity(
        models.ReplacementPreparation,
        preparation_values,
        field="preparation_id",
        prefix="finance_v26_225_repair_preparation:",
    )
    ledger = (
        tmp_path
        / subject.LEDGER_DIR
        / f"{hashlib.sha256(forged_authorization.authorization_id.encode()).hexdigest()}.json"
    )
    forged = replace(
        prepared,
        repository_root=tmp_path,
        package_root=tmp_path / "trusted_data_synthesis",
        output_dir=tmp_path / subject.OUTPUT_DIR,
        ledger_path=ledger,
        authorization=forged_authorization,
        authorization_bytes=forged_bytes,
        preparation=forged_preparation,
    )
    with pytest.raises(ValueError, match="refreshed execution parent"):
        subject._consume(forged, refreshed=preflight_objects)  # noqa: SLF001
    assert not ledger.exists()
    assert not forged.output_dir.exists()


def test_repair_directive_hashes_are_exact() -> None:
    assert len(models.REPAIR_DIRECTIVE.encode("utf-8")) == 42
    assert hashlib.sha256(models.REPAIR_DIRECTIVE.encode()).hexdigest() == (
        models.REPAIR_DIRECTIVE_SHA256
    )
    assert len(models.CONDITIONAL_RUN_DIRECTIVE.encode("utf-8")) == 69
    assert hashlib.sha256(models.CONDITIONAL_RUN_DIRECTIVE.encode()).hexdigest() == (
        models.CONDITIONAL_RUN_DIRECTIVE_SHA256
    )
