"""Synthetic separate recovery budgets; no real API, credential or task admission."""

import json
from copy import deepcopy

import pytest
import run_cross_market_text_schema_recovery_20260927 as m
from test_cross_market_review_pilot import packet as synthetic_packet


@pytest.fixture
def case(tmp_path, monkeypatch):
    monkeypatch.setattr(m.base, "RAW", tmp_path)
    monkeypatch.setattr(m.original, "RAW", tmp_path / "parent-mainline")
    monkeypatch.setattr(m.capacity, "RECORD", m.original.RAW / "capacity.json")
    monkeypatch.setattr(m, "RECORD", m.original.RAW / "recovery.json")
    m.base.write(m.capacity.RECORD, {"id": "synthetic-capacity"})
    packet = synthetic_packet(1)
    path = tmp_path / "original-material" / "packet.json"
    m.base.write(path, packet)
    packet = m.base.read(path)
    row = dict(
        packet_id=packet["id"],
        raw_object_id=packet["raw_object_id"],
        reference=m.original.ref(path),
    )
    plan = dict(id="synthetic-parent", packet_universe=[row])
    revision = dict(id="synthetic-recovery", parent_protocol_id=plan["id"])
    m.base.write(m.RECORD, revision)
    return dict(
        packet=packet, row=row, plan=plan, revision=revision, revision_ref=m.original.ref(m.RECORD)
    )


def exhaust_original(case, count=2):
    paths = []
    for attempt in range(1, count + 1):
        path = m.original.RAW / "attempts" / m.original.key_for(case["packet"]["id"]) / str(attempt)
        m.base.write(
            path / "reservation.json",
            dict(
                protocol_id=case["plan"]["id"],
                packet_id=case["packet"]["id"],
                attempt=attempt,
                request_sha256="synthetic",
            ),
        )
        m.base.write(path / "outcome.json", dict(status="TECHNICAL_FAILURE_NOT_REFUNDED"))
        paths.extend((path / "reservation.json", path / "outcome.json"))
    return {path: path.read_bytes() for path in paths}


def response(raw, fault=None):
    body = json.loads(raw)
    view = json.loads(body["messages"][1]["content"])
    payload = dict(
        packet_id=view["packet_id"],
        findings=[],
        uncertainties=[],
        segments_reviewed=[s["segment_key"] for s in view["indexed_segments"]],
    )
    if fault in {"duplicate", "reversed_dates"}:
        line = next(line["line_id"] for s in view["indexed_segments"] for line in s["lines"])
        finding = dict(
            id="f1",
            boundary_a=line,
            boundary_b=line,
            metric="revenue",
            kind="uncertain",
            scope="consolidated",
            aggregation="unknown",
            period_start=None,
            period_end=None,
            reason="Synthetic source uncertainty",
        )
        if fault == "duplicate":
            payload["findings"] = [finding, deepcopy(finding)]
        else:
            finding.update(period_start="2023-01-01", period_end="2021-12-31")
            payload["findings"] = [finding]
    return m.base.encode(
        dict(
            model=body["model"],
            id="synthetic-response",
            usage=dict(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            choices=[
                dict(
                    finish_reason="stop",
                    message=dict(content="{" if fault == "invalid_JSON" else json.dumps(payload)),
                )
            ],
        )
    ), "synthetic-request"


def namespace(case, monkeypatch, sender):
    real_factory = m.capacity.transport_namespace

    def factory(reference):
        transport = real_factory(reference)
        provider = transport.Provider
        transport.Provider = lambda output, key: provider(output, key, sender=sender)
        return transport

    monkeypatch.setattr(m.capacity, "transport_namespace", factory)
    return m.execution_namespace(case["revision"], case["revision_ref"])


def test_recovery_preserves_old_attempts_and_binds_exact_new_request(case, monkeypatch):
    before = exhaust_original(case)
    calls = []

    def sender(raw, key):
        calls.append(raw)
        assert len(list((m.original.RAW / "recovery_attempts").glob("*/*/reservation.json"))) == 1
        return response(raw)

    ns = namespace(case, monkeypatch, sender)
    result = ns["review_packet"](case["plan"], case["row"], "SYNTHETIC_ONLY")
    assert len(calls) == 1 and result["protocol_id"] == case["plan"]["id"]
    assert all(path.read_bytes() == value for path, value in before.items())
    execution = result["execution"]
    assert execution["schema_recovery_revision_id"] == case["revision"]["id"]
    assert execution["schema_recovery_revision_reference"] == case["revision_ref"]
    assert execution["schema_recovery_extra_attempt"] == 1
    recorded = m.base.read(execution["request_reference"]["path"])
    assert recorded["raw_body_sha256"] == m.base.sha(calls[0])
    _, original_request = ns["request_for"](case["packet"], case["row"]["reference"])
    body = json.loads(calls[0])
    assert body["messages"][1] == original_request["messages"][1]
    assert body["messages"][0]["content"].endswith(m.CLARIFICATION)
    assert body["model"] == m.original.MODEL and body["max_tokens"] == 4096
    assert ns["SCRIPT"] == m.SCRIPT
    assert ns["review_packet"](case["plan"], case["row"], "SYNTHETIC_ONLY") == result
    assert len(calls) == 1


def test_parent_normal_review_runs_first_and_success_never_uses_recovery(case, monkeypatch):
    calls = []

    def sender(raw, key):
        calls.append(raw)
        assert m.CLARIFICATION not in json.loads(raw)["messages"][0]["content"]
        return response(raw)

    ns = namespace(case, monkeypatch, sender)
    result = ns["review_packet"](case["plan"], case["row"], "SYNTHETIC_ONLY")
    assert result is not None and len(calls) == 1
    assert not list((m.original.RAW / "recovery_attempts").glob("*/*/reservation.json"))
    assert "schema_recovery_revision_id" not in result["execution"]


def test_only_one_old_attempt_cannot_enter_extra_budget(case, monkeypatch):
    exhaust_original(case, count=1)
    ns = namespace(case, monkeypatch, lambda *_: pytest.fail("not exhausted"))
    assert (
        m.recover_packet(
            ns, case["revision"], case["revision_ref"], case["plan"], case["row"], "SYNTHETIC_ONLY"
        )
        is None
    )
    assert not list((m.original.RAW / "recovery_attempts").glob("*/*/reservation.json"))


@pytest.mark.parametrize("fault", ["duplicate", "reversed_dates", "invalid_JSON"])
def test_original_validator_stays_strict_and_extra_attempts_stop_at_two(case, monkeypatch, fault):
    before = exhaust_original(case)
    calls = []

    def sender(raw, key):
        calls.append(raw)
        return response(raw, fault)

    ns = namespace(case, monkeypatch, sender)
    assert ns["review_packet"](case["plan"], case["row"], "SYNTHETIC_ONLY") is None
    assert len(calls) == 2
    assert ns["review_packet"](case["plan"], case["row"], "SYNTHETIC_ONLY") is None
    assert len(calls) == 2
    assert all(path.read_bytes() == value for path, value in before.items())
    outcomes = [
        m.base.read(path)
        for path in (m.original.RAW / "recovery_attempts").glob("*/*/outcome.json")
    ]
    assert len(outcomes) == 2 and all(
        r["status"] == "TECHNICAL_FAILURE_NOT_REFUNDED" for r in outcomes
    )
    assert not list((m.original.RAW / "packet_reviews").glob("*.json"))


def test_global128_budget_cannot_be_replenished(case, monkeypatch):
    exhaust_original(case)
    for index in range(m.MAX_EXTRA_POSTS):
        m.base.write(
            m.original.RAW / "recovery_attempts" / f"old-{index}" / "1" / "reservation.json",
            dict(synthetic_spent=True),
        )
    ns = namespace(case, monkeypatch, lambda *_: pytest.fail("global budget exhausted"))
    assert ns["review_packet"](case["plan"], case["row"], "SYNTHETIC_ONLY") is None
    assert len(list((m.original.RAW / "recovery_attempts").glob("*/*/reservation.json"))) == 128


def test_unsettled_extra_attempt_not_replayed_only_second_remains(case, monkeypatch):
    exhaust_original(case)
    ns = namespace(case, monkeypatch, lambda raw, _: response(raw))
    _, request = m.clarified_request(ns, case["packet"], case["row"]["reference"])
    directory = (
        m.original.RAW / "recovery_attempts" / m.original.key_for(case["packet"]["id"]) / "1"
    )
    m.base.write(
        directory / "reservation.json",
        dict(
            recovery_revision_id=case["revision"]["id"],
            protocol_id=case["plan"]["id"],
            packet_id=case["packet"]["id"],
            request_sha256=m.base.sha(m.base.encode(request)),
        ),
    )
    before = (directory / "reservation.json").read_bytes()
    result = ns["review_packet"](case["plan"], case["row"], "SYNTHETIC_ONLY")
    assert result["execution"]["schema_recovery_extra_attempt"] == 2
    assert (directory / "reservation.json").read_bytes() == before
    assert m.base.read(directory / "outcome.json")["status"] == "INTERRUPTED_UNSETTLED_NOT_REFUNDED"


def test_foreign_packet_cannot_enter_recovery_budget(case, monkeypatch):
    exhaust_original(case)
    ns = namespace(case, monkeypatch, lambda *_: pytest.fail("foreign source"))
    row = dict(case["row"], packet_id="not-registered")
    with pytest.raises(ValueError, match="registered_parent_packet_only"):
        m.recover_packet(
            ns, case["revision"], case["revision_ref"], case["plan"], row, "SYNTHETIC_ONLY"
        )
