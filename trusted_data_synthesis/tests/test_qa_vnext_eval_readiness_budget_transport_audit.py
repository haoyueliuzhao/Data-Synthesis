"""Independent, fake-sender-only cross-purpose billing and transport controls."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_eval_readiness import budget, transport
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import HTTPResponse
from trusted_synthesis.experiments.finance_qa_vnext_surface_build.budget import BudgetRejected
from trusted_synthesis.experiments.finance_qa_vnext_task_build.archive import record

PRIOR = [{"id": "actual_prior", "tokens": 221538}]
GATE_KEYS = (
    "panel_quota_complete",
    "actual_period_semantics_passed",
    "complete_trajectory_qualification_passed",
    "live_transport_controls_passed",
    "training_catalog_locked",
    "original_package_consumer_registered",
    "increment_source_semantics_passed",
    "new_original_CPU_representation_passed",
)
MESSAGES = [{"role": "user", "content": "完整公共任务，返回首次 Final。"}]


def create(tmp_path, *, global_cap=budget.GLOBAL_CAP, register=True):
    value = budget.ResearchLedger(
        tmp_path / "research.sqlite3", "stage-audit", prior_debits=PRIOR, global_cap=global_cap
    )
    value.register([f"new-{i}" for i in range(17)], [])
    sessions = []
    if register:
        gate = {
            "id": "gate",
            "status": "READY_FOR_FIXED_COLLECTION",
            **dict.fromkeys(GATE_KEYS, True),
        }
        sessions = value.register_collection(
            [{"task_id": "task", "family": "control"}], gate_id="gate", gate=gate
        )
    return value, sessions


def response(
    *,
    model=transport.MODEL,
    status=200,
    usage=None,
    content='{"Final":{"value":"1"}}',
    complete=True,
):
    body = {
        "model": model,
        "choices": [
            {
                "message": {"content": content, "reasoning_content": "PRIVATE-REASONING"},
                "finish_reason": "stop",
            }
        ],
    }
    body["usage"] = (
        {"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12} if usage is None else usage
    )
    return HTTPResponse(status, json.dumps(body).encode(), complete=complete)


class FakeSender:
    def __init__(self, value):
        self.value, self.calls = value, []

    def send(self, request, *, api_key):
        self.calls.append((request, api_key))
        return self.value


def invoke(value, session, output, sender):
    provider = transport.Provider(
        value, session["session_id"], output, "not-a-real-key", sender=sender
    )
    context = {"session_id": session["session_id"], "identity": {"task_id": session["task_id"]}}
    return provider(MESSAGES, context)


@pytest.mark.parametrize("missing", GATE_KEYS)
def test_each_gate_predicate_blocks_registration_and_zero_send(tmp_path, missing):
    value, _ = create(tmp_path, register=False)
    gate = {"id": "gate", "status": "READY_FOR_FIXED_COLLECTION", **dict.fromkeys(GATE_KEYS, True)}
    gate[missing] = False
    with pytest.raises(BudgetRejected):
        value.register_collection(
            [{"task_id": "task", "family": "control"}], gate_id="gate", gate=gate
        )
    sender = FakeSender(response())
    with pytest.raises(ValueError):
        invoke(
            value, {"session_id": "unregistered", "task_id": "task"}, tmp_path / "requests", sender
        )
    assert not sender.calls
    assert value.snapshot()["Teacher_request_reservations"] == 0


def test_request_body_exact_public_projection_and_mock_not_training(tmp_path):
    value, sessions = create(tmp_path)
    sender = FakeSender(response())
    observed = invoke(value, sessions[0], tmp_path / "requests", sender)
    assert observed["authentic_model_origin"] is False
    request_id = observed["evidence"]["request_id"]
    directory = tmp_path / "requests" / request_id
    request = json.loads((directory / "request.json").read_bytes())
    projected = json.loads((directory / "public_response.json").read_bytes())
    assert request["body_json"] == sender.calls[0][0]["body_json"]
    assert hashlib.sha256(request["body_json"].encode()).hexdigest() == request["body_sha256"]
    assert request["body"] == json.loads(request["body_json"])
    assert "PRIVATE-REASONING" not in (directory / "public_response.json").read_text()
    assert projected["private_reasoning_present"] and not projected["private_reasoning_text_saved"]
    assert projected["public_content"] == observed["raw_response"]
    assert value.snapshot()["Teacher_conservative_charged_tokens"] == 12
    session = {
        "session_id": sessions[0]["session_id"],
        "identity": {"task_id": "task"},
        "turns": [{"input_messages": MESSAGES, "raw_response": observed["raw_response"]}],
    }
    with pytest.raises(ValueError, match="mock_sender"):
        transport.verify_receipts(session, value, tmp_path / "requests")


def test_unknown_usage_stays_fully_charged_across_reopen(tmp_path):
    value, sessions = create(tmp_path)
    with pytest.raises(transport.FatalStudyError):
        invoke(value, sessions[0], tmp_path / "requests", FakeSender(response(usage={})))
    reopened = budget.ResearchLedger(
        tmp_path / "research.sqlite3", "stage-audit", prior_debits=PRIOR
    )
    snapshot = reopened.snapshot()
    assert snapshot["teacher_reservations"][0]["state"] == "usage_unknown"
    assert snapshot["Teacher_conservative_charged_tokens"] == budget.TEACHER_RESERVATION
    assert snapshot["cumulative_conservative_debit"] == 221538 + budget.TEACHER_RESERVATION
    with pytest.raises(BudgetRejected):
        reopened.reserve_teacher(sessions[0]["session_id"])


@pytest.mark.parametrize("mark_sent", [False, True])
def test_unsettled_reservation_never_reclaimed(tmp_path, mark_sent):
    value, sessions = create(tmp_path)
    lease = value.reserve_teacher(sessions[0]["session_id"])
    if mark_sent:
        value.mark_teacher_sent(lease["request_id"])
    reopened = budget.ResearchLedger(
        tmp_path / "research.sqlite3", "stage-audit", prior_debits=PRIOR
    )
    assert reopened.snapshot()["Teacher_conservative_charged_tokens"] == budget.TEACHER_RESERVATION
    with pytest.raises(BudgetRejected):
        reopened.reserve_teacher(sessions[0]["session_id"])


def test_cross_purpose_atomic_race_reserves_only_one_when_both_do_not_fit(tmp_path):
    maximum = 221538 + budget.TEACHER_RESERVATION + 9728 - 1
    value, sessions = create(tmp_path, global_cap=maximum)
    barrier = Barrier(2)

    def reserve(kind):
        barrier.wait()
        try:
            return (
                value.reserve("new-0")
                if kind == "rewrite"
                else value.reserve_teacher(sessions[0]["session_id"])
            )
        except BudgetRejected:
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(reserve, ("rewrite", "teacher")))
    assert sum(result is not None for result in results) == 1
    reopened = budget.ResearchLedger(
        tmp_path / "research.sqlite3", "stage-audit", prior_debits=PRIOR, global_cap=maximum
    )
    assert reopened.snapshot()["cumulative_conservative_debit"] <= maximum


def test_same_session_concurrent_reservations_do_not_create_two_inflight(tmp_path):
    value, sessions = create(tmp_path)
    barrier = Barrier(8)

    def reserve(_):
        barrier.wait()
        try:
            return value.reserve_teacher(sessions[0]["session_id"])
        except BudgetRejected:
            return None

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(reserve, range(8)))
    assert sum(result is not None for result in results) == 1
    assert value.snapshot()["Teacher_request_reservations"] == 1


def test_per_session_32_responses_are_persistent_maximum(tmp_path):
    value, sessions = create(tmp_path)
    for _ in range(32):
        lease = value.reserve_teacher(sessions[0]["session_id"])
        value.mark_teacher_sent(lease["request_id"])
        value.settle_teacher(
            lease["request_id"],
            usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            http_success=True,
            response_model=transport.MODEL,
            outcome="public_response_received",
        )
    reopened = budget.ResearchLedger(
        tmp_path / "research.sqlite3", "stage-audit", prior_debits=PRIOR
    )
    with pytest.raises(BudgetRejected, match="32_response"):
        reopened.reserve_teacher(sessions[0]["session_id"])


@pytest.mark.parametrize("kind", ["teacher", "rewrite"])
def test_one_purpose_usage_breach_blocks_both_consumers(tmp_path, kind):
    value, sessions = create(tmp_path)
    if kind == "teacher":
        lease = value.reserve_teacher(sessions[0]["session_id"])
        value.mark_teacher_sent(lease["request_id"])
        value.settle_teacher(
            lease["request_id"],
            usage={
                "prompt_tokens": budget.INPUT_ALLOWANCE + 1,
                "completion_tokens": 1,
                "total_tokens": budget.INPUT_ALLOWANCE + 2,
            },
            http_success=True,
            response_model=transport.MODEL,
            outcome="public_response_received",
        )
    else:
        lease = value.reserve("new-0")
        value.mark_sent(lease["request_id"])
        value.settle(
            lease["request_id"],
            usage={"prompt_tokens": 8193, "completion_tokens": 1, "total_tokens": 8194},
            http_success=True,
            response_model=transport.MODEL,
            outcome="response_received",
        )
    with pytest.raises(BudgetRejected):
        value.reserve("new-1")
    with pytest.raises(BudgetRejected):
        value.reserve_teacher(sessions[1]["session_id"])


@pytest.mark.parametrize("kind", ["wrong_model", "HTTP401", "HTTP403"])
def test_fatal_model_or_auth_error_persistently_stops_all_new_consumers(tmp_path, kind):
    value, sessions = create(tmp_path)
    reply = response(
        model="wrong" if kind == "wrong_model" else transport.MODEL,
        status=401 if kind == "HTTP401" else 403 if kind == "HTTP403" else 200,
    )
    with pytest.raises(transport.FatalStudyError):
        invoke(value, sessions[0], tmp_path / "requests", FakeSender(reply))
    reopened = budget.ResearchLedger(
        tmp_path / "research.sqlite3", "stage-audit", prior_debits=PRIOR
    )
    with pytest.raises(BudgetRejected):
        reopened.reserve_teacher(sessions[1]["session_id"])
    with pytest.raises(BudgetRejected):
        reopened.reserve("new-0")


def test_oversize_input_has_zero_reservations_and_zero_sender_calls(tmp_path):
    value, sessions = create(tmp_path)
    sender = FakeSender(response())
    provider = transport.Provider(
        value, sessions[0]["session_id"], tmp_path / "requests", "not-a-key", sender=sender
    )
    with pytest.raises(ValueError, match="input_bound"):
        provider(
            [{"role": "user", "content": "字" * 50000}],
            {"session_id": sessions[0]["session_id"], "identity": {"task_id": "task"}},
        )
    assert not sender.calls
    assert value.snapshot()["Teacher_request_reservations"] == 0


@pytest.mark.parametrize("purpose", ["teacher", "rewrite"])
def test_fatal_blocks_already_reserved_but_unsent_requests_after_reopen(tmp_path, purpose):
    value, sessions = create(tmp_path)
    lease = (
        value.reserve_teacher(sessions[1]["session_id"])
        if purpose == "teacher"
        else value.reserve("new-0")
    )
    with pytest.raises(transport.FatalStudyError):
        invoke(value, sessions[0], tmp_path / "requests", FakeSender(response(status=401)))
    reopened = budget.ResearchLedger(
        tmp_path / "research.sqlite3", "stage-audit", prior_debits=PRIOR
    )
    with pytest.raises(BudgetRejected):
        if purpose == "teacher":
            reopened.mark_teacher_sent(lease["request_id"])
        else:
            reopened.mark_sent(lease["request_id"])
    rows = (
        reopened.snapshot()["teacher_reservations"]
        if purpose == "teacher"
        else reopened.snapshot()["reservations"]
    )
    assert (
        next(row for row in rows if row["request_id"] == lease["request_id"])["state"] == "reserved"
    )
    assert (
        next(row for row in rows if row["request_id"] == lease["request_id"])["charged_tokens"]
        == lease["reserved_tokens"]
    )


def test_reopening_fatal_ledger_never_clears_persistent_stop(tmp_path):
    value, sessions = create(tmp_path)
    with pytest.raises(transport.FatalStudyError):
        invoke(value, sessions[0], tmp_path / "requests", FakeSender(response(model="wrong")))
    for _ in range(3):
        reopened = budget.ResearchLedger(
            tmp_path / "research.sqlite3", "stage-audit", prior_debits=PRIOR
        )
        with reopened.connection() as db:
            assert (
                db.execute("SELECT value FROM metadata WHERE key='study_fatal'").fetchone()
                is not None
            )
        with pytest.raises(BudgetRejected):
            reopened.reserve_teacher(sessions[1]["session_id"])
        with pytest.raises(BudgetRejected):
            reopened.reserve("new-1")


@pytest.mark.parametrize("count", [18, 27, 28])
def test_new_target_registration_never_exceeds_17(tmp_path, count):
    value = budget.ResearchLedger(tmp_path / "research.sqlite3", "stage-audit", prior_debits=PRIOR)
    with pytest.raises(BudgetRejected):
        value.register([str(i) for i in range(count)], [])


def test_tampered_response_model_is_joined_to_ledger_not_only_content(tmp_path):
    value, sessions = create(tmp_path)
    observed = invoke(value, sessions[0], tmp_path / "requests", FakeSender(response()))
    directory = tmp_path / "requests" / observed["evidence"]["request_id"]
    # Controlled test-only mutation bypasses the explicit mock guard so we can
    # isolate the next receipt checks. It does not assert authentic provenance.
    request = json.loads((directory / "request.json").read_bytes())
    result = json.loads((directory / "public_response.json").read_bytes())
    receipt = json.loads((directory / "receipt.json").read_bytes())
    request["live_http_sender"] = receipt["live_http_sender"] = True
    result["response_model"] = "tampered-other-model"

    def rerender(value, kind):
        return record(kind, **{k: v for k, v in value.items() if k not in {"id", "schema_version"}})

    result = rerender(result, "Teacher_public_response")
    receipt["response_id"] = result["id"]
    for name, contents, kind in (
        ("request.json", request, "Teacher_public_request"),
        ("public_response.json", result, "Teacher_public_response"),
        ("receipt.json", receipt, "Teacher_request_receipt"),
    ):
        (directory / name).write_text(json.dumps(rerender(contents, kind)))
    session = {
        "session_id": sessions[0]["session_id"],
        "identity": {"task_id": "task"},
        "turns": [{"input_messages": MESSAGES, "raw_response": observed["raw_response"]}],
    }
    with pytest.raises(ValueError):
        transport.verify_receipts(session, value, tmp_path / "requests")
