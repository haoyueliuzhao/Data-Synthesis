"""Synthetic HTTP evidence exercises the reader; no real API request is made."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.domains.finance.qa_vnext.callbacks import PublicFixtureCallback
from trusted_synthesis.domains.finance.qa_vnext.program_adapter import ProgramTaskAdapter
from trusted_synthesis.domains.finance.qa_vnext.protocol import contract
from trusted_synthesis.domains.finance.qa_vnext.runner import build_catalog
from trusted_synthesis.domains.finance.qa_vnext.runtime import PublicQARuntime
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import (
    identity,
    record,
    sha,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.qualification import (
    compare_qualified_sessions,
    qualify_session,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import (
    HTTPResponse,
    HTTPSendError,
    HttpxSender,
    OnlineModelCallback,
    TransportConfig,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def adapter() -> ProgramTaskAdapter:
    catalog = build_catalog(ROOT)
    cases, _ = catalog.frozen_source_cases(ROOT, task_types=("registered_cross_metric_comparison",))
    return ProgramTaskAdapter(cases[0], catalog.registry)


def _registration(
    adapter: Any, config: TransportConfig, *, maximum_submissions: int = 32
) -> dict[str, Any]:
    return record(
        "session_registration",
        session_id="synthetic-provider-evidence-control",
        label="C01",
        ordinal=0,
        round=1,
        task_group="C",
        task_type=adapter.context["task_type"],
        task_id=adapter.context["task_id"],
        context_id=adapter.context["id"],
        protocol_id=contract()["id"],
        registry_hash=strict_canonical_hash(adapter.registry.manifest()),
        model_configuration_id=config.as_record()["id"],
        run_condition_id="synthetic-test-condition",
        maximum_actions=min(12, maximum_submissions),
        maximum_submissions=maximum_submissions,
        maximum_provider_attempts=32,
        replacement_allowed=False,
        reference_route=None,
        independent_initial_state=True,
    )


def _start(registration: dict[str, Any], status: str = "started") -> dict[str, Any]:
    return record(
        "session_start",
        status=status,
        reason="synthetic local qualification test",
        session_id=registration["session_id"],
        registered_id=registration["id"],
    )


def _run(
    tmp_path: Path,
    adapter: Any,
    monkeypatch: pytest.MonkeyPatch,
    *,
    behavior: str = "success",
    live_type: bool = True,
    maximum_submissions: int = 32,
    config: TransportConfig | None = None,
) -> dict[str, Any]:
    config = config or TransportConfig()
    registration = _registration(adapter, config, maximum_submissions=maximum_submissions)
    fixture = PublicFixtureCallback()
    calls: list[dict[str, Any]] = []

    def synthetic_send(
        _sender: Any, request: dict[str, Any], *, api_key: str | None
    ) -> HTTPResponse:
        calls.append(request)
        public = json.loads(request["messages"][1]["content"])
        if behavior == "timeout" and request["attempt_index"] == 1:
            raise HTTPSendError("transport.timeout")
        if behavior == "partial_timeout":
            raise HTTPSendError(
                "transport.timeout", HTTPResponse(200, b'{"choices":[', complete=False)
            )
        raw = fixture.generate(public)
        if behavior == "correction" and request["attempt_index"] == 0:
            raw = b'{"kind":"action"}'
        content = raw.decode("utf-8")
        if behavior == "no_response":
            content = ""
        message: dict[str, Any] = {"role": "assistant", "content": content}
        if behavior == "condition_violation":
            message["tool_calls"] = [{"id": "unexpected", "type": "function"}]
        envelope = {
            "id": "synthetic-http-response-" + str(request["attempt_index"]),
            "object": "chat.completion",
            "model": "wrong-model" if behavior == "wrong_model" else "deepseek-v4-pro-0813",
            "choices": [{"index": 0, "finish_reason": "stop", "message": message}],
            "usage": {"prompt_tokens": 123, "completion_tokens": 45, "total_tokens": 168},
        }
        return HTTPResponse(
            200, canonical_json_bytes(envelope), headers=(("content-type", "application/json"),)
        )

    # This patches the I/O boundary, not qualification. All resulting files live
    # under pytest's temporary directory and are never cohort/model samples.
    monkeypatch.setattr(HttpxSender, "send", synthetic_send)

    class MockSender:
        send = synthetic_send

    callback = OnlineModelCallback(
        config,
        session_id=registration["session_id"],
        evidence_directory=tmp_path / "transport",
        sender=None if live_type else MockSender(),
        api_key="unit-test-no-network",
    )
    runtime = PublicQARuntime(
        adapter,
        callback,
        tmp_path / "runtime",
        max_actions=registration["maximum_actions"],
        max_submissions=maximum_submissions,
    )
    session = runtime.run()
    callback.finalize()
    start = _start(registration)
    qualification = qualify_session(
        adapter,
        registration,
        session,
        tmp_path / "runtime",
        tmp_path / "transport",
        start_record=start,
    )
    return {
        "session": session,
        "qualification": qualification,
        "registration": registration,
        "start": start,
        "calls": calls,
        "callback": callback,
    }


def _requalify(result: dict[str, Any], tmp_path: Path, adapter: Any) -> dict[str, Any]:
    return qualify_session(
        adapter,
        result["registration"],
        result["session"],
        tmp_path / "runtime",
        tmp_path / "transport",
        start_record=result["start"],
    )


def _reseal_transport(path: Path) -> None:
    old = json.loads((path / "manifest.json").read_bytes())
    ledger = json.loads((path / "ledger.json").read_bytes())
    members = []
    for file in sorted(path.rglob("*")):
        if file.is_file() and file.name != "manifest.json":
            data = file.read_bytes()
            members.append(
                {"path": file.relative_to(path).as_posix(), "sha256": sha(data), "bytes": len(data)}
            )
    manifest = record(
        "transport_manifest",
        session_id=old["session_id"],
        ledger_id=ledger["id"],
        members=members,
        self_excluding=True,
        write_events=ledger["write_events"]
        + [
            {"kind": "file_fsync", "path": "ledger.json"},
            {"kind": "directory_fsync", "path": "ledger.json"},
        ],
    )
    (path / "manifest.json").write_bytes(canonical_json_bytes(manifest))


def test_exact_http_bytes_are_linked_to_every_runtime_submission(
    tmp_path: Path,
    adapter: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _run(tmp_path, adapter, monkeypatch)
    qualification = result["qualification"]
    assert qualification["status"] == "success", qualification["errors"]
    identity(qualification, "qualification")
    assert qualification["model_origin_verified"] and qualification["qualified"]
    assert qualification["export_eligible"] and qualification["condition_valid"]
    assert len(qualification["verified_turns"]) == qualification["provider_attempt_count"] == 3
    assert qualification["session_id"] == result["session"]["id"]
    assert qualification["registered_session_id"] == result["registration"]["session_id"]
    for turn in qualification["verified_turns"]:
        request = json.loads((tmp_path / "transport" / turn["request_path"]).read_bytes())
        response = json.loads((tmp_path / "transport" / turn["response_path"]).read_bytes())
        event = result["session"]["events"][turn["turn_index"]]
        assert request["messages"][1]["content"] == canonical_json_bytes(event["request"]).decode()
        assert (
            response["choices"][0]["message"]["content"].encode()
            == (tmp_path / "runtime" / f"turns/{turn['turn_index']:03d}_response.txt").read_bytes()
        )
    assert compare_qualified_sessions(qualification, qualification)["relation"] == "equivalent"


def test_mock_transport_cannot_become_model_evidence_from_response_model_field(
    tmp_path: Path,
    adapter: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _run(tmp_path, adapter, monkeypatch, live_type=False)
    qualification = result["qualification"]
    assert qualification["evidence_complete"], qualification["errors"]
    assert qualification["domain_audit"]["qualified"]
    assert qualification["control_evidence"] and not qualification["model_origin_verified"]
    assert not qualification["qualified"] and not qualification["export_eligible"]


@pytest.mark.parametrize("behavior", ["timeout", "no_response", "partial_timeout", "wrong_model"])
def test_complete_observed_failure_is_not_unknown(
    tmp_path: Path,
    adapter: Any,
    monkeypatch: pytest.MonkeyPatch,
    behavior: str,
) -> None:
    result = _run(tmp_path, adapter, monkeypatch, behavior=behavior)
    qualification = result["qualification"]
    assert qualification["status"] == "known_failure", qualification["errors"]
    assert qualification["evidence_complete"] and qualification["trajectory_valid"]
    assert qualification["qa_valid"] is None and qualification["end_to_end_success"] is False
    assert qualification["qualified"] is False and not qualification["export_eligible"]
    assert qualification["depth_scope"] == "reached_prefix"
    if behavior == "timeout":
        assert qualification["provider_attempt_count"] == 2
        assert qualification["runtime_submission_count"] == 1
        assert qualification["depth_metrics"]["actual_action_dependency_semantic_depth"] == 1
    else:
        assert qualification["provider_attempt_count"] == 1
        assert qualification["runtime_submission_count"] == 0


def test_missing_observed_response_remains_unknown_not_zero_success(
    tmp_path: Path,
    adapter: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _run(tmp_path, adapter, monkeypatch)
    (tmp_path / "transport/attempts/000_http_response.body").unlink()
    qualification = _requalify(result, tmp_path, adapter)
    assert qualification["status"] == "unknown"
    assert not qualification["evidence_complete"]
    assert qualification["end_to_end_success"] is qualification["qualified"] is None
    assert qualification["export_eligible"] is False


def test_explicit_not_started_and_missing_start_evidence_are_distinct(
    tmp_path: Path, adapter: Any
) -> None:
    registration = _registration(adapter, TransportConfig())
    pending = qualify_session(
        adapter,
        registration,
        None,
        tmp_path / "runtime",
        tmp_path / "transport",
        start_record=_start(registration, "not_started"),
    )
    unknown = qualify_session(
        adapter, registration, None, tmp_path / "runtime", tmp_path / "transport"
    )
    assert pending["status"] == "not_started" and pending["provider_attempt_count"] == 0
    assert pending["end_to_end_success"] is None
    assert unknown["status"] == "unknown" and unknown["end_to_end_success"] is None


@pytest.mark.parametrize("start_evidence", ["valid", "bad_identity", "wrong_parent"])
def test_started_without_session_preserves_only_verified_start_fact(
    tmp_path: Path,
    adapter: Any,
    start_evidence: str,
) -> None:
    registration = _registration(adapter, TransportConfig())
    start = _start(registration)
    if start_evidence == "bad_identity":
        start = {**start, "reason": "changed without rebinding identity"}
    elif start_evidence == "wrong_parent":
        fields = {key: value for key, value in start.items() if key not in {"id", "schema_version"}}
        start = record("session_start", **{**fields, "registered_id": "another-registration"})
    qualification = qualify_session(
        adapter,
        registration,
        None,
        tmp_path / "runtime",
        tmp_path / "transport",
        start_record=start,
    )
    assert qualification["status"] == "unknown"
    assert qualification["execution_started"] is (True if start_evidence == "valid" else None)
    assert qualification["terminated"] is None
    assert (
        qualification["qa_valid"]
        is qualification["qualified"]
        is qualification["end_to_end_success"]
        is None
    )
    assert qualification["provider_attempt_count"] is None
    assert not qualification["evidence_complete"] and not qualification["export_eligible"]
    if start_evidence == "valid":
        assert qualification["reason"] == "started_session_evidence_missing"
        assert qualification["errors"] == []
    else:
        assert qualification["errors"]


def test_budget_exhaustion_and_presend_input_resource_stop_keep_prefix_depth(
    tmp_path: Path,
    adapter: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    budget = _run(tmp_path / "budget", adapter, monkeypatch, maximum_submissions=2)
    resource = _run(
        tmp_path / "resource",
        adapter,
        monkeypatch,
        config=TransportConfig(system_prompt="oversize-control:" + "x" * 100_000),
    )
    for result in (budget, resource):
        qualification = result["qualification"]
        assert qualification["status"] == "known_failure", qualification["errors"]
        assert qualification["evidence_complete"] and qualification["qa_valid"] is None
        assert qualification["end_to_end_success"] is False
        assert qualification["depth_scope"] == "reached_prefix"
    assert budget["qualification"]["provider_attempt_count"] == 2
    assert resource["qualification"]["provider_attempt_count"] == 0
    assert resource["qualification"]["runtime_submission_count"] == 0
    assert not resource["calls"]


def test_qualified_corrected_session_stays_exportable_when_projection_is_unknown(
    tmp_path: Path,
    adapter: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _run(tmp_path, adapter, monkeypatch, behavior="correction")
    qualification = result["qualification"]
    assert qualification["status"] == "success", qualification["errors"]
    assert qualification["qualified"] and qualification["export_eligible"]
    assert qualification["projection_status"] == "undetermined"
    assert qualification["quotient_assignment_id"] is None
    assert len(qualification["verified_turns"]) == 4
    assert qualification["verified_turns"][0]["admitted"] is False
    assert compare_qualified_sessions(qualification, qualification)["relation"] == "undetermined"


def test_complete_condition_violation_is_separate_from_task_qa_failure(
    tmp_path: Path,
    adapter: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _run(tmp_path, adapter, monkeypatch, behavior="condition_violation")
    qualification = result["qualification"]
    assert qualification["evidence_complete"], qualification["errors"]
    assert qualification["qa_valid"] is True and qualification["domain_audit"]["qualified"]
    assert qualification["condition_valid"] is False
    assert qualification["status"] == "known_failure" and qualification["qualified"] is False


def test_future_state_http_messages_cannot_replace_actual_runtime_condition(
    tmp_path: Path,
    adapter: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _run(tmp_path, adapter, monkeypatch)
    transport = tmp_path / "transport"
    metadata_path = transport / "attempts/000_http_request.json"
    request = json.loads(metadata_path.read_bytes())
    body = request["body"]
    body["messages"][1]["content"] = canonical_json_bytes(
        result["session"]["events"][1]["request"]
    ).decode()
    data = canonical_json_bytes(body)
    fields = {key: value for key, value in request.items() if key not in {"id", "schema_version"}}
    fields.update(
        body=body,
        messages=body["messages"],
        body_json=data.decode(),
        body_sha256=sha(data),
        body_byte_count=len(data),
        input_admission_upper_bound=len(data) + 1024,
    )
    metadata_path.write_bytes(canonical_json_bytes(record("http_request", **fields)))
    (transport / "attempts/000_http_request.body").write_bytes(data)
    _reseal_transport(transport)
    qualification = _requalify(result, tmp_path, adapter)
    assert qualification["status"] == "unknown"
    assert qualification["errors"][0]["code"] == "online.actual_http_messages_or_configuration"


def test_old_protocol_registration_does_not_borrow_current_qa_result(
    tmp_path: Path,
    adapter: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _run(tmp_path, adapter, monkeypatch)
    fields = {
        key: value
        for key, value in result["registration"].items()
        if key not in {"id", "schema_version"}
    }
    result["registration"] = record(
        "session_registration", **{**fields, "protocol_id": "old-share-protocol"}
    )
    result["start"] = _start(result["registration"])
    qualification = _requalify(result, tmp_path, adapter)
    assert qualification["status"] == "unknown" and not qualification["export_eligible"]
    assert qualification["errors"][0]["code"] == "online.protocol_baseline"


@pytest.mark.parametrize("attack", ["unreserved_send", "send_before_reservation"])
def test_resealed_transport_cannot_hide_attempts_or_reverse_reservation_order(
    tmp_path: Path,
    adapter: Any,
    monkeypatch: pytest.MonkeyPatch,
    attack: str,
) -> None:
    result = _run(tmp_path, adapter, monkeypatch)
    transport = tmp_path / "transport"
    ledger = json.loads((transport / "ledger.json").read_bytes())
    journal = ledger["write_events"]
    send = next(item for item in journal if item["kind"] == "send")
    if attack == "unreserved_send":
        journal.append({**send, "attempt_index": 99})
    else:
        journal.remove(send)
        before = next(
            index
            for index, item in enumerate(journal)
            if item.get("kind") == "file_fsync"
            and item.get("path") == "attempts/000_reservation.json"
        )
        journal.insert(before, send)
    fields = {key: value for key, value in ledger.items() if key not in {"id", "schema_version"}}
    (transport / "ledger.json").write_bytes(
        canonical_json_bytes(record("transport_ledger", **fields))
    )
    _reseal_transport(transport)
    qualification = _requalify(result, tmp_path, adapter)
    assert qualification["status"] == "unknown" and qualification["end_to_end_success"] is None
    assert qualification["errors"][0]["code"] == (
        "online.journal_attempt_count"
        if attack == "unreserved_send"
        else "online.reservation_before_send"
    )


def test_not_started_does_not_erase_an_already_observed_resource_stop(
    tmp_path: Path, adapter: Any
) -> None:
    registration = _registration(adapter, TransportConfig())
    stops = tmp_path / "transport/stops"
    stops.mkdir(parents=True)
    (stops / "000_outcome.json").write_bytes(b"already observed source stop")
    qualification = qualify_session(
        adapter,
        registration,
        None,
        tmp_path / "runtime",
        tmp_path / "transport",
        start_record=_start(registration, "not_started"),
    )
    assert qualification["status"] == "unknown"
    assert qualification["errors"][0]["code"] == "online.not_started_conflicting_evidence"
