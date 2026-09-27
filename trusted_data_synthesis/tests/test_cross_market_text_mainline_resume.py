"""Synthetic packet resume contracts; no actual API, credential read or task PASS."""

import json
from copy import deepcopy

import pytest
import run_cross_market_text_mainline_20260927 as m
from test_cross_market_review_pilot import packet as synthetic_packet


@pytest.fixture
def case(tmp_path, monkeypatch):
    monkeypatch.setattr(m.base, "RAW", tmp_path)
    monkeypatch.setattr(m, "RAW", tmp_path / "mainline")
    packet = synthetic_packet(1)
    path = tmp_path / "frozen-parent" / "packet.json"
    m.base.write(path, packet)
    row = dict(packet_id=packet["id"], raw_object_id=packet["raw_object_id"], reference=m.ref(path))
    return dict(
        packet=packet,
        row=row,
        plan=dict(id="synthetic-mainline"),
        parent=path,
        parent_bytes=path.read_bytes(),
    )


def response(raw, *, malformed=False):
    body = json.loads(raw)
    source = json.loads(body["messages"][1]["content"])
    payload = dict(
        packet_id=source["packet_id"],
        segments_reviewed=[r["segment_key"] for r in source["indexed_segments"]],
        findings=[],
        uncertainties=[],
    )
    return m.base.encode(
        dict(
            model=body["model"],
            id="synthetic-response",
            choices=[
                dict(
                    finish_reason="stop",
                    message=dict(content="{" if malformed else json.dumps(payload)),
                )
            ],
            usage=dict(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )
    ), "synthetic-request"


def injected(monkeypatch, sender):
    provider = m.transport.Provider
    monkeypatch.setattr(
        m.transport, "Provider", lambda directory, key: provider(directory, key, sender=sender)
    )


def test_success_is_reused_without_new_attempt_and_parent_not_modified(case, monkeypatch):
    calls = []

    def sender(raw, key):
        calls.append(raw)
        assert len(list((m.RAW / "attempts").glob("*/*/reservation.json"))) == len(calls)
        return response(raw)

    injected(monkeypatch, sender)
    first = m.review_packet(case["plan"], case["row"], "SYNTHETIC_ONLY")
    assert first["status"] == "REAL_TEXT_TABLE_SEMANTIC_RESPONSE_SAVED_NOT_TASK_CERTIFIED"
    assert first == m.review_packet(case["plan"], case["row"], "SYNTHETIC_ONLY")
    assert len(calls) == 1 and "passed" not in first
    assert case["parent"].read_bytes() == case["parent_bytes"]


@pytest.mark.parametrize("changed", ["protocol_id", "packet_id", "packet_sha256"])
def test_cached_foreign_identity_rejected_before_any_new_send(case, monkeypatch, changed):
    injected(monkeypatch, lambda raw, _: response(raw))
    first = m.review_packet(case["plan"], case["row"], "SYNTHETIC_ONLY")
    body = {k: deepcopy(v) for k, v in first.items() if k not in {"id", "schema_version"}}
    body[changed] = "foreign"
    result_path = m.RAW / "packet_reviews" / (m.key_for(case["packet"]["id"]) + ".json")
    m.base.write(result_path, m.base.record(m.semantic.PACKET_KIND, **body), immutable=False)
    monkeypatch.setattr(m.transport, "Provider", lambda *_: pytest.fail("no cached replay"))
    with pytest.raises(ValueError, match="cached_packet_identity"):
        m.review_packet(case["plan"], case["row"], "SYNTHETIC_ONLY")


def test_two_failed_attempts_are_charged_and_resume_cannot_make_third(case, monkeypatch):
    calls = []

    def sender(raw, key):
        calls.append(raw)
        return response(raw, malformed=True)

    injected(monkeypatch, sender)
    assert m.review_packet(case["plan"], case["row"], "SYNTHETIC_ONLY") is None
    assert len(calls) == 2
    assert m.review_packet(case["plan"], case["row"], "SYNTHETIC_ONLY") is None
    assert len(calls) == 2
    outcomes = [m.base.read(path) for path in (m.RAW / "attempts").glob("*/*/outcome.json")]
    assert len(outcomes) == 2
    assert all(row["status"] == "TECHNICAL_FAILURE_NOT_REFUNDED" for row in outcomes)
    assert not list((m.RAW / "task_reviews").glob("*.json"))


def test_unsettled_first_attempt_is_preserved_only_second_is_available(case, monkeypatch):
    stem = m.key_for(case["packet"]["id"])
    directory = m.RAW / "attempts" / stem / "1"
    m.base.write(
        directory / "reservation.json",
        dict(
            protocol_id=case["plan"]["id"],
            packet_id=case["packet"]["id"],
            attempt=1,
            possibly_billed=True,
        ),
    )
    original = (directory / "reservation.json").read_bytes()
    calls = []

    def sender(raw, key):
        calls.append(raw)
        assert (m.RAW / "attempts" / stem / "2" / "reservation.json").exists()
        return response(raw)

    injected(monkeypatch, sender)
    result = m.review_packet(case["plan"], case["row"], "SYNTHETIC_ONLY")
    assert result is not None and len(calls) == 1
    assert (directory / "reservation.json").read_bytes() == original
    assert m.base.read(directory / "outcome.json")["status"] == "INTERRUPTED_UNSETTLED_NOT_REFUNDED"
    assert len(list((m.RAW / "attempts").glob("*/*/reservation.json"))) == 2


def test_both_unsettled_attempts_cannot_be_refunded(case, monkeypatch):
    stem = m.key_for(case["packet"]["id"])
    for attempt in (1, 2):
        m.base.write(
            m.RAW / "attempts" / stem / str(attempt) / "reservation.json",
            dict(
                protocol_id=case["plan"]["id"],
                packet_id=case["packet"]["id"],
                attempt=attempt,
                possibly_billed=True,
            ),
        )
    monkeypatch.setattr(m.transport, "Provider", lambda *_: pytest.fail("no third attempt"))
    assert m.review_packet(case["plan"], case["row"], "SYNTHETIC_ONLY") is None
    assert len(list((m.RAW / "attempts").glob("*/*/outcome.json"))) == 2
