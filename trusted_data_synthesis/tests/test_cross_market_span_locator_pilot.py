"""Third execution adapter: synthetic senders only, no real APIs or documents."""

import json

import pytest
import run_cross_market_span_locator_pilot_20260927 as pilot
from test_cross_market_review_pilot import setup_pilot  # noqa: F401


@pytest.fixture
def span_pilot(request, monkeypatch):
    data = request.getfixturevalue("setup_pilot")
    data["output"] = data["output"].parent / "span-third-pilot"
    monkeypatch.setattr(pilot, "RAW", data["output"])
    data["plan"]["requests"] = []
    for packet, row in zip(data["packets"][:5], data["rows"][:5], strict=True):
        for lane in pilot.core.LANES:
            view, wire, _ = pilot.request_for(packet, row["reference"], lane)
            data["plan"]["requests"].append(
                dict(
                    packet_id=packet["id"],
                    lane=lane,
                    projection_id=view["id"],
                    request_sha256=pilot.base.sha(wire.body),
                )
            )
    return data


def run_job(data, number=0, lane="discovery"):
    return pilot.run_job(
        data["plan"],
        data["parent"],
        data["manifest"],
        data["approval"],
        data["rows"][number],
        lane,
        "SYNTHETIC_SECRET",
    )


def envelope(raw, failure=None):
    body = json.loads(raw)
    view = json.loads(body["messages"][1]["content"])
    line = view["indexed_segments"][0]["lines"][0]["line_id"]
    payload = dict(
        packet_id=view["packet_id"],
        segments_reviewed=[s["segment_key"] for s in view["indexed_segments"]],
        findings=[
            dict(
                id="one",
                boundary_a=line,
                boundary_b=line,
                metric="revenue",
                kind="uncertain",
                period_start=None,
                period_end=None,
                reason="Synthetic range, not a financial fact",
            )
        ],
        uncertainties=[],
    )
    if failure == "unknown":
        payload["findings"][0]["boundary_a"] = "UNKNOWN"
    if failure == "old_contract":
        row = payload["findings"][0]
        row["line_start"], row["line_end"] = row.pop("boundary_a"), row.pop("boundary_b")
    content = '{"broken": "\n"}' if failure == "invalid_JSON" else json.dumps(payload)
    return pilot.base.encode(
        dict(
            id="synthetic-span-response",
            model=body["model"],
            usage=dict(prompt_tokens=8, completion_tokens=4, total_tokens=12),
            choices=[dict(finish_reason="stop", message=dict(content=content))],
        )
    ), "synthetic-header"


def install_sender(monkeypatch, sender):
    original = pilot.transport.Provider
    monkeypatch.setattr(
        pilot.transport, "Provider", lambda root, key: original(root, key, sender=sender)
    )


def test_exact_ten_nonempty_calls_retained_as_raw_groups_and_fragments(span_pilot, monkeypatch):
    data = span_pilot
    before = {p: p.read_bytes() for p in data["parent_root"].rglob("*.json")}
    old_raw, old_validator = pilot.core.RAW, pilot.core.validate_scan
    calls = []

    def sender(raw, key):
        assert len(list((data["output"] / "API_attempts").glob("*.json"))) == len(calls) + 1
        calls.append(raw)
        return envelope(raw)

    install_sender(monkeypatch, sender)
    results = [run_job(data, n, lane) for n in range(5) for lane in pilot.core.LANES]
    assert len(calls) == 10
    for result in results:
        assert result["status"] == "ASSISTANCE_RESPONSE_SAVED_NOT_ADMITTED"
        detail = result["result"]
        assert detail["span_mapping_proof"]["raw_locator_group_count"] == 1
        assert detail["span_mapping_proof"]["derived_quote_fragment_count"] == 1
        assert detail["span_mapping_proof"]["financial_observation_count"] is None
        assert json.loads(result["provider_response"]["content"]) == detail["raw_span_payload"]
        assert "boundary_a" in detail["raw_span_payload"]["findings"][0]
        assert "quote" not in detail["raw_span_payload"]["findings"][0]
        assert detail["payload"]["findings"][0]["evidence_fragment_not_financial_observation"]
    assert run_job(data) == results[0] and len(calls) == 10
    assert before == {p: p.read_bytes() for p in data["parent_root"].rglob("*.json")}
    assert pilot.core.RAW == old_raw and pilot.core.validate_scan is old_validator


@pytest.mark.parametrize("failure", ["unknown", "old_contract", "invalid_JSON"])
def test_failure_never_repaired_or_replayed(span_pilot, monkeypatch, failure):
    sent = []

    def sender(raw, key):
        sent.append(raw)
        return envelope(raw, failure)

    install_sender(monkeypatch, sender)
    value = run_job(span_pilot)
    assert value["status"] == "SCAN_ATTEMPT_FAILED_NOT_REFUNDED"
    assert run_job(span_pilot) == value and len(sent) == 1


@pytest.mark.parametrize(
    "path", ["API_attempts/a.1.json", "physical_requests/a/request.json", "scan_results/a.1.json"]
)
def test_unregistered_state_rejected_before_parent(span_pilot, monkeypatch, path):
    pilot.base.write(span_pilot["output"] / path, {"synthetic": True})
    monkeypatch.setattr(pilot.previous, "protocol", lambda *_: pytest.fail("must not read parent"))
    with pytest.raises(ValueError, match="span_pilot_no_unregistered_attempts"):
        pilot.register(span_pilot["output"])


def test_unsettled_job_not_replayed(span_pilot, monkeypatch):
    job = pilot.core.job_key(span_pilot["packets"][0]["id"], "discovery")
    pilot.base.write(span_pilot["output"] / "API_attempts" / (job + ".1.json"), {"reserved": True})
    install_sender(monkeypatch, lambda *_: pytest.fail("must not send"))
    with pytest.raises(ValueError, match="span_pilot_unsettled_attempt_no_replay"):
        run_job(span_pilot)
