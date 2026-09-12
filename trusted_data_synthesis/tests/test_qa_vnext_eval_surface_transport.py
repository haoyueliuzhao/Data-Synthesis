"""Public-contract transport controls: temporary wallets and explicit mock senders only."""

import copy
import hashlib
import io
import json
import urllib.error

import pytest
from test_qa_vnext_eval_surface_budget import wallet
from test_qa_vnext_eval_surface_guard import KINDS, fixture

from trusted_synthesis.experiments.finance_qa_vnext_eval_surface import budget, guard, transport
from trusted_synthesis.experiments.finance_qa_vnext_surface_build.budget import BudgetRejected
from trusted_synthesis.experiments.finance_qa_vnext_task_build.archive import record

KEY = "mock-credential-not-a-real-key-84970351"


def setup(tmp_path, *, kind="arithmetic_mean", mutate=None):
    bank, legacy = wallet(tmp_path)
    public, identity = fixture(kind, noncalendar=True)
    spec = guard.build_spec(public, identity)
    if mutate:
        body = {k: v for k, v in spec.items() if k not in {"schema_version", "id"}}
        mutate(body)
        spec = record("evaluation_rewrite_spec", **body)
    bank.register_evaluation(
        [
            {
                "task_id": identity["task_id"],
                "split": "dev",
                "identity": identity,
                "spec_sha256": budget.canonical_sha256(spec),
            },
        ],
        policy_id="execution-policy",
        parent_panel_manifest_id=identity["parent_manifest_id"],
    )
    return bank, legacy, spec, identity


def content(template, second=None):
    rows = [{"rewrite_version": transport.VERSION, "question_template": template}]
    if second is not None:
        rows.append({"rewrite_version": transport.VERSION, "question_template": second})
    return json.dumps({"rewrites": rows}, ensure_ascii=False)


def envelope(raw_content, *, used=None, model=budget.MODEL):
    return json.dumps(
        {
            "model": model,
            "usage": used
            if used is not None
            else {
                "prompt_tokens": 123,
                "completion_tokens": 45,
                "total_tokens": 168,
            },
            "choices": [
                {
                    "message": {
                        "content": raw_content,
                        "reasoning_content": "PRIVATE_REASONING_NEVER_SAVED",
                    }
                }
            ],
        }
    ).encode()


@pytest.mark.parametrize("kind", KINDS)
def test_exact_public_model_contract_only_one_send_and_original_candidates(tmp_path, kind):
    bank, _, spec, identity = setup(tmp_path, kind=kind)
    raw = content(
        spec["canonical_template"], spec["canonical_template"].replace("Calculate", "Determine")
    )
    calls = []
    wire = envelope(raw)

    def sender(body, key):
        calls.append((copy.deepcopy(body), key))
        return wire

    result = transport.EvaluationProvider(
        identity, spec, bank, tmp_path / "evidence", KEY, sender=sender
    ).request()
    assert len(calls) == 1 and calls[0][1] == KEY
    body = calls[0][0]
    assert set(body) == {"model", "messages", "thinking", "response_format", "max_tokens", "stream"}
    assert body["thinking"] == {"type": "disabled"} and body["max_tokens"] == 1536
    assert json.loads(body["messages"][1]["content"]) == spec["model_contract"]
    sent = json.dumps(body)
    for excluded in (
        "0000012345",
        "2020-09-27",
        "2019-09-30",
        "public_family",
        "public-original",
        "old_manifest",
    ):
        assert excluded not in sent
    assert result["candidates"] == json.loads(raw)["rewrites"]
    assert result["raw_content"] == raw and result["structure_errors"] == []
    directory = tmp_path / "evidence" / "evaluation_requests" / result["request_id"]
    request = json.loads((directory / "request.json").read_text())
    response = json.loads((directory / "public_response.json").read_text())
    assert request["body_json"].encode() == json.dumps(body, ensure_ascii=False).encode()
    assert request["body_sha256"] == hashlib.sha256(request["body_json"].encode()).hexdigest()
    assert request["serialized_body_bytes"] + 1024 == request["admitted_input_bound"] <= 8192
    assert request["live_HTTP_sender"] is False
    assert response["raw_public_content"] == raw
    assert response["received_body_sha256"] == hashlib.sha256(wire).hexdigest()
    assert response["private_reasoning_present"] and not response["private_reasoning_text_saved"]
    assert all(
        "PRIVATE_REASONING_NEVER_SAVED" not in path.read_text() for path in directory.iterdir()
    )
    assert bank.snapshot()["cumulative_conservative_debit"] == 221538 + 168


def test_contract_failure_never_auto_retries_one_explicit_repair_only(tmp_path):
    bank, _, spec, identity = setup(tmp_path)
    calls = []

    def sender(body, key):
        calls.append(body)
        return envelope("not JSON" if len(calls) == 1 else content(spec["canonical_template"]))

    provider = transport.EvaluationProvider(identity, spec, bank, tmp_path, KEY, sender=sender)
    first = provider.request()
    assert first["candidates"] == [] and first["structure_errors"] and len(calls) == 1
    second = provider.request(repair_reason=["evaluation.response_structure"])
    assert second["candidates"] and len(calls) == 2
    assert calls[0]["messages"][1] == calls[1]["messages"][1]
    assert "evaluation.response_structure" in calls[1]["messages"][0]["content"]
    with pytest.raises(BudgetRejected):
        provider.request(repair_reason=["evaluation.response_structure"])
    assert len(calls) == 2


@pytest.mark.parametrize(
    "reason", [[], "free text", ["unsafe with whitespace"], ["x" * 129], ["x"] * 33]
)
def test_unbounded_repair_is_rejected_before_lease_or_send(tmp_path, reason):
    bank, _, spec, identity = setup(tmp_path)
    provider = transport.EvaluationProvider(
        identity, spec, bank, tmp_path, KEY, sender=lambda *_: pytest.fail("send")
    )
    with pytest.raises(BudgetRejected):
        provider.request(repair_reason=reason)
    assert bank.snapshot()["eval_request_reservations"] == 0


@pytest.mark.parametrize("status", [None, 429, 500, 401, 403])
def test_transport_failure_unknown_hold_and_only_auth_is_global(tmp_path, status):
    bank, legacy, spec, identity = setup(tmp_path)
    calls = []

    def sender(*args):
        calls.append(args)
        if status is None:
            raise TimeoutError("unobserved billing")
        raise urllib.error.HTTPError(
            "https://example.invalid", status, "mock failure", {}, io.BytesIO(KEY.encode())
        )

    provider = transport.EvaluationProvider(identity, spec, bank, tmp_path, KEY, sender=sender)
    with pytest.raises(transport.EvaluationTransportError) as raised:
        provider.request()
    assert raised.value.global_fatal is (status in {401, 403})
    assert raised.value.receipt["settlement"]["charged_tokens"] == 9728
    assert raised.value.receipt["settlement"]["state"] == "usage_unknown"
    with pytest.raises(BudgetRejected):
        provider.request(repair_reason=["evaluation.response_structure"])
    assert len(calls) == 1
    legacy.register(["unp"], [])
    if status in {401, 403}:
        with pytest.raises(BudgetRejected):
            legacy.reserve("unp")
    else:
        legacy.reserve("unp")
    failure = tmp_path / "evaluation_requests" / raised.value.request_id / "failure.json"
    assert KEY not in failure.read_text()


@pytest.mark.parametrize(
    "mutation",
    [
        "no_usage",
        "bad_total",
        "boolean_count",
        "wrong_model",
        "object_model",
        "malformed",
        "duplicate",
        "over_cap",
    ],
)
def test_complete_http_invalid_billing_or_model_is_persistent_global_stop(tmp_path, mutation):
    bank, legacy, spec, identity = setup(tmp_path)
    value = json.loads(envelope(content(spec["canonical_template"])))
    if mutation == "no_usage":
        del value["usage"]
    elif mutation == "bad_total":
        value["usage"]["total_tokens"] = 1
    elif mutation == "boolean_count":
        value["usage"]["prompt_tokens"] = True
    elif mutation == "wrong_model":
        value["model"] = "wrong-model"
    elif mutation == "object_model":
        value["model"] = {"model": budget.MODEL}
    elif mutation == "over_cap":
        value["usage"] = {"prompt_tokens": 9000, "completion_tokens": 1600, "total_tokens": 10600}
    wire = json.dumps(value).encode()
    if mutation == "malformed":
        wire = b'{"broken":'
    elif mutation == "duplicate":
        wire = b'{"model":"deepseek-flash","model":"deepseek-flash"}'
    provider = transport.EvaluationProvider(
        identity, spec, bank, tmp_path, KEY, sender=lambda *_: wire
    )
    with pytest.raises(transport.EvaluationTransportError) as raised:
        provider.request()
    assert raised.value.global_fatal and bank.snapshot()["persisted_study_stop"]
    legacy.register(["unp"], [])
    with pytest.raises(BudgetRejected):
        legacy.reserve("unp")
    if mutation == "over_cap":
        assert raised.value.receipt["settlement"]["charged_tokens"] == 10600
    if mutation in {"malformed", "duplicate"}:
        assert raised.value.receipt["received_body_sha256"] == hashlib.sha256(wire).hexdigest()


@pytest.mark.parametrize(
    "raw",
    [
        '{"rewrites":[],"rewrites":[]}',
        '{"rewrites":[],"extra":1}',
        '{"rewrites":[]}',
        '{"rewrites":[{"rewrite_version":"wrong","question_template":"x"}]}',
        '{"rewrites":[{"rewrite_version":"evaluation_surface_rewrite.v1","question_template":"x","extra":1}]}',
        '{"rewrites":NaN}',
    ],
)
def test_closed_candidate_json_rejects_without_selecting_or_reordering(raw):
    candidates, errors = transport.parse_candidates(raw)
    assert candidates == [] and errors


@pytest.mark.parametrize("mutation", ["identity", "spec_hash", "contract_extra", "oversized"])
def test_identity_spec_and_full_body_bound_preflight_zero_attempts(tmp_path, mutation):
    def alter(body):
        if mutation == "contract_extra":
            body["model_contract"].update(private_answer=3)
        if mutation == "oversized":
            body["model_contract"].update(forbidden=["x" * 10000])

    bank, _, spec, identity = setup(tmp_path, mutate=alter)
    if mutation == "identity":
        identity = {**identity, "family": "changed"}
    elif mutation == "spec_hash":
        spec = record(
            "evaluation_rewrite_spec",
            **{k: v for k, v in spec.items() if k not in {"schema_version", "id", "original_base"}},
            original_base="changed",
        )
    with pytest.raises(BudgetRejected):
        transport.EvaluationProvider(
            identity, spec, bank, tmp_path, KEY, sender=lambda *_: pytest.fail("send")
        )
    assert bank.snapshot()["eval_request_reservations"] == 0


def test_output_symlink_is_rejected_before_lease(tmp_path):
    bank, _, spec, identity = setup(tmp_path)
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(BudgetRejected, match="symlinks"):
        transport.EvaluationProvider(identity, spec, bank, link, KEY)
    provider = transport.EvaluationProvider(identity, spec, bank, tmp_path, KEY)
    (tmp_path / "evaluation_requests").symlink_to(target, target_is_directory=True)
    with pytest.raises(BudgetRejected, match="symlinks"):
        provider.request()
    assert bank.snapshot()["eval_request_reservations"] == 0


def test_credential_echo_is_redacted_and_stops_all_purposes(tmp_path):
    bank, _, spec, identity = setup(tmp_path)
    raw = content(spec["canonical_template"] + KEY)
    provider = transport.EvaluationProvider(
        identity, spec, bank, tmp_path, KEY, sender=lambda *_: envelope(raw)
    )
    with pytest.raises(transport.EvaluationTransportError) as raised:
        provider.request()
    assert raised.value.global_fatal
    directory = tmp_path / "evaluation_requests" / raised.value.request_id
    assert all(KEY not in path.read_text() for path in directory.iterdir())


def test_concurrent_stop_after_reserve_retains_not_sent_lease_and_receipt(tmp_path, monkeypatch):
    bank, _, spec, identity = setup(tmp_path)
    original_mark = bank.mark_evaluation_sent

    def racing_mark(identifier):
        bank.halt("another_request_stopped_study")
        original_mark(identifier)

    monkeypatch.setattr(bank, "mark_evaluation_sent", racing_mark)
    provider = transport.EvaluationProvider(
        identity, spec, bank, tmp_path, KEY, sender=lambda *_: pytest.fail("send")
    )
    with pytest.raises(transport.EvaluationTransportError) as raised:
        provider.request()
    failure = raised.value.receipt
    assert raised.value.global_fatal and failure["failure_code"] == "NOT_SENT_AFTER_STUDY_STOP"
    assert not failure["sent"] and failure["lower_level_attempts"] == 0
    assert failure["retained_charge"] == 9728 and failure["settlement"] is None
    row = bank.snapshot()["eval_reservations"][0]
    assert row["state"] == "reserved" and row["charged_tokens"] == 9728
    assert bank.snapshot()["eval_sent_request_count"] == 0
    directory = tmp_path / "evaluation_requests" / raised.value.request_id
    assert (directory / "request.json").is_file() and (directory / "failure.json").is_file()


def test_request_evidence_write_failure_is_global_not_sent_with_full_lease(tmp_path, monkeypatch):
    bank, _, spec, identity = setup(tmp_path)
    original_write = transport.write_json

    def failing_write(path, value):
        if path.name == "request.json":
            raise OSError("mock read-only request storage")
        original_write(path, value)

    monkeypatch.setattr(transport, "write_json", failing_write)
    provider = transport.EvaluationProvider(
        identity, spec, bank, tmp_path, KEY, sender=lambda *_: pytest.fail("send")
    )
    with pytest.raises(transport.EvaluationTransportError) as raised:
        provider.request()
    failure = raised.value.receipt
    assert failure["failure_code"] == "NOT_SENT_EVIDENCE_WRITE_FAILED"
    assert failure["reservation"]["request_id"] == raised.value.request_id
    assert not failure["sent"] and failure["settlement"] is None
    state = bank.snapshot()
    assert state["persisted_study_stop"] and state["eval_sent_request_count"] == 0
    assert state["eval_reservations"][0]["state"] == "reserved"
    assert state["cumulative_conservative_debit"] == 221538 + 9728
