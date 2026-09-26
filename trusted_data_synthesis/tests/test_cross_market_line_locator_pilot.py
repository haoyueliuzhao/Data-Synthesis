"""Second-pilot isolation tests: synthetic sources/senders, no actual API or PDF."""

import json

import pytest
import run_cross_market_line_locator_pilot_20260927 as pilot
from test_cross_market_review_pilot import setup_pilot  # noqa: F401


@pytest.mark.parametrize(
    "relative", ["API_attempts/hash.1.json", "physical_requests/hash/request.json"]
)
def test_unregistered_attempt_traces_block_before_parent_work(line_pilot, monkeypatch, relative):
    pilot.base.write(line_pilot["output"] / relative, {"synthetic": True})
    monkeypatch.setattr(pilot.prior, "protocol", lambda *_: pytest.fail("parent must not run"))
    with pytest.raises(ValueError, match="line_pilot_no_unregistered_attempts"):
        pilot.register(line_pilot["output"])


@pytest.fixture
def line_pilot(request, monkeypatch):
    data = request.getfixturevalue("setup_pilot")
    data["previous_output"] = data["output"]
    data["output"] = data["output"].parent / "separate-line-pilot"
    monkeypatch.setattr(pilot, "RAW", data["output"])
    data["plan"]["requests"] = []
    for packet, row in zip(data["packets"][:5], data["rows"][:5], strict=True):
        for lane in pilot.core.LANES:
            view, rendered, _ = pilot.request_for(packet, row["reference"], lane)
            data["plan"]["requests"].append(
                dict(
                    packet_id=packet["id"],
                    lane=lane,
                    projection_id=view["id"],
                    request_sha256=pilot.base.sha(rendered.body),
                    request_bytes=len(rendered.body),
                )
            )
    return data


def sender_response(raw, *, invalid=False, old_character_protocol=False):
    body = json.loads(raw)
    source = json.loads(body["messages"][1]["content"])
    first = source["indexed_segments"][0]
    line = first["lines"][0]["line_id"]
    payload = dict(
        packet_id=source["packet_id"],
        segments_reviewed=[s["segment_key"] for s in source["indexed_segments"]],
        findings=[
            dict(
                id="f1",
                line_start="nonexistent" if invalid else line,
                line_end=line,
                metric="revenue",
                kind="uncertain",
                period_start=None,
                period_end=None,
                reason="Synthetic assistance locator, not financial admission",
            )
        ],
        uncertainties=[],
    )
    if old_character_protocol:
        payload["findings"] = [
            dict(
                finding_id="old",
                segment_id=first["segment_id"],
                start=0,
                end=1,
                quote="S",
                metric_id="revenue",
                classification="uncertain",
                period_start=None,
                period_end=None,
                reasoning="Original protocol must not be silently repaired",
            )
        ]
    return pilot.base.encode(
        dict(
            id="synthetic-line-response",
            model=body["model"],
            usage=dict(prompt_tokens=8, completion_tokens=4, total_tokens=12),
            choices=[dict(finish_reason="stop", message=dict(content=json.dumps(payload)))],
        )
    ), "synthetic-line-request"


def inject_sender(monkeypatch, sender):
    provider = pilot.transport.Provider
    monkeypatch.setattr(
        pilot.transport, "Provider", lambda output, key: provider(output, key, sender=sender)
    )


def run_job(data, number=0, lane="discovery"):
    return pilot.run_job(
        data["plan"],
        data["parent"],
        data["manifest"],
        data["approval"],
        data["rows"][number],
        lane,
        "SYNTHETIC_ONLY",
    )


def test_new_request_not_reused_old_quote_body_and_original_text_unchanged(line_pilot):
    data = line_pilot
    packet, row = data["packets"][0], data["rows"][0]
    old, old_rendered, _ = pilot.prior.request_for(packet, row["reference"], "discovery")
    view, rendered, body = pilot.request_for(packet, row["reference"], "discovery")
    assert old["id"] != view["id"] and old_rendered.body != rendered.body
    assert pilot.transport.request_bytes(body) == rendered.body
    indexed = view["payload"]["indexed_segments"]
    assert ["".join(line["text"] for line in s["lines"]) for s in indexed] == [
        s["text"] for s in packet["segments"]
    ]
    assert body["max_tokens"] == 4096
    assert len(rendered.body) <= pilot.transport.MAX_REQUEST_BYTES


def test_actual_line_validator_routed_only_in_new_namespace(line_pilot, monkeypatch):
    data = line_pilot
    original = (
        pilot.core.RAW,
        pilot.core.validate_scan,
        pilot.core.request_payload,
        pilot.prior.RAW,
        pilot.prior.request_for,
    )
    inject_sender(monkeypatch, lambda raw, _: sender_response(raw))
    result = run_job(data)
    assert result["status"] == "ASSISTANCE_RESPONSE_SAVED_NOT_ADMITTED"
    assert result["passed"] is False and result["attempt"] == 1
    review = result["result"]
    raw_line = review["raw_line_payload"]["findings"][0]
    derived = review["payload"]["findings"][0]
    assert "line_start" in raw_line and "quote" not in raw_line
    assert derived["quote"] == data["packets"][0]["segments"][0]["text"]
    assert derived["start"] == 0 and derived["end"] == len(derived["quote"])
    assert not review["line_mapping_proof"]["earlier_character_response_repair"]
    assert not review["line_mapping_proof"]["semantic_certificate_created"]
    assert json.loads(result["provider_response"]["content"])["findings"][0] == raw_line
    assert original == (
        pilot.core.RAW,
        pilot.core.validate_scan,
        pilot.core.request_payload,
        pilot.prior.RAW,
        pilot.prior.request_for,
    )
    assert not data["previous_output"].exists()


def test_ten_new_attempts_do_not_refund_or_reuse_previous_ten(line_pilot, monkeypatch):
    data = line_pilot
    for i in range(10):
        pilot.base.write(
            data["previous_output"] / "API_attempts" / f"old-{i}.json",
            dict(previous_failed_or_passed_attempt=i, refundable=False),
        )
    before = {p: p.read_bytes() for p in data["previous_output"].rglob("*.json")}
    calls = []

    def sender(raw, _):
        calls.append(raw)
        assert len(list((data["output"] / "API_attempts").glob("*.json"))) == len(calls)
        return sender_response(raw)

    inject_sender(monkeypatch, sender)
    results = [run_job(data, i, lane) for i in range(5) for lane in pilot.core.LANES]
    assert len(calls) == len(results) == 10
    assert all(
        r["attempt"] == 1 and r["status"] == "ASSISTANCE_RESPONSE_SAVED_NOT_ADMITTED"
        for r in results
    )
    assert len(list((data["output"] / "API_attempts").glob("*.json"))) == 10
    assert all(path.read_bytes() == value for path, value in before.items())
    assert not list((data["previous_output"] / "scan_results").glob("*.json"))
    assert run_job(data)["id"] == results[0]["id"] and len(calls) == 10


@pytest.mark.parametrize("mode", ["unknown_line", "old_character_reply"])
def test_invalid_line_or_old_protocol_is_preserved_failure_without_retry(
    line_pilot,
    monkeypatch,
    mode,
):
    calls = []

    def sender(raw, _):
        calls.append(raw)
        return sender_response(
            raw,
            invalid=mode == "unknown_line",
            old_character_protocol=mode == "old_character_reply",
        )

    inject_sender(monkeypatch, sender)
    first = run_job(line_pilot)
    assert first["status"] == "SCAN_ATTEMPT_FAILED_NOT_REFUNDED"
    assert first == run_job(line_pilot) and len(calls) == 1
    assert first["passed"] is False and first["attempt"] == 1


def test_unsettled_new_reservation_blocks_replay(line_pilot, monkeypatch):
    data = line_pilot
    job = pilot.core.job_key(data["packets"][0]["id"], "discovery")
    pilot.base.write(data["output"] / "API_attempts" / (job + ".1.json"), {"reserved": True})
    inject_sender(monkeypatch, lambda *_: pytest.fail("must not replay physical attempt"))
    with pytest.raises(ValueError, match="unsettled_attempt_no_replay"):
        run_job(data)


def test_cached_result_cannot_be_credited_to_wrong_parent(line_pilot, monkeypatch):
    data = line_pilot
    job = pilot.core.job_key(data["packets"][0]["id"], "discovery")
    pilot.base.write(
        data["output"] / "scan_results" / (job + ".1.json"),
        pilot.base.record(
            "cross_market_source_scan_result",
            protocol_id="not-this-parent",
            packet_id=data["packets"][0]["id"],
            lane="discovery",
            attempt=1,
        ),
    )
    inject_sender(monkeypatch, lambda *_: pytest.fail("wrong cached result must not send"))
    with pytest.raises(ValueError, match="cached_job_identity"):
        run_job(data)


def test_new_save_cannot_write_into_previous_pilot(line_pilot):
    with pytest.raises(ValueError, match="line_pilot_output_root"):
        pilot.save(line_pilot["previous_output"] / "forbidden.json", {})
