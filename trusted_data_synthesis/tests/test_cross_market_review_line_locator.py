"""Prospective line-ID protocol tests; no live requests or old-reply repairs."""

import copy
import json

import cross_market_review_line_locator_20260927 as m
import pytest


def fixture():
    pages = [
        dict(page=1, text="收入 10\r\n利润 😀\r\n尾行"),
        dict(page=2, text=""),
        dict(page=3, text="现金流 20\n另行\u2028末行"),
    ]
    intervals = [
        dict(
            task_id=f"t{i}",
            metric_id=m.core.METRICS[i % 4],
            periods=[
                ["2021-01-01", "2021-12-31"],
                ["2022-01-01", "2022-12-31"],
                ["2023-01-01", "2023-12-31"],
            ],
        )
        for i in range(28)
    ]
    packet = m.core.build_packets(
        dict(
            raw_object_id="r", sha256="a" * 64, original_url="https://official.example/report.pdf"
        ),
        dict(path="/frozen/text.json", sha256="b" * 64, bytes=500),
        pages,
        task_intervals=intervals,
    )[0]
    payload = m.base.encode(packet)
    reference = dict(path="/frozen/packet.json", sha256=m.base.sha(payload), bytes=len(payload))
    return packet, m.project_packet(packet, reference)


def reply(packet, projection):
    lines = projection["line_ledger"]["lines"]
    return dict(
        packet_id=packet["id"],
        segments_reviewed=[s["segment_key"] for s in projection["line_ledger"]["segments"]],
        findings=[
            dict(
                id="f1",
                line_start=lines[0]["line_id"],
                line_end=lines[1]["line_id"],
                metric="revenue",
                kind="uncertain",
                period_start=None,
                period_end=None,
                reason="Actual period needs independent adjudication.",
            )
        ],
        uncertainties=[dict(segment_key="S001", reason="Empty text; original visuals pending.")],
    )


def test_all_source_characters_segments_intervals_and_blank_pages_preserved():
    packet, projection = fixture()
    assert projection["original_segments"] == packet["segments"]
    assert (
        projection["payload"]["registered_candidate_intervals"]
        == packet["registered_candidate_intervals"]
    )
    assert projection["payload"]["metric_universe"] == list(m.core.METRICS)
    for original, indexed in zip(
        packet["segments"], projection["payload"]["indexed_segments"], strict=True
    ):
        assert "".join(line["text"] for line in indexed["lines"]) == original["text"]
        assert indexed["segment_id"] == original["segment_id"]
    assert projection["payload"]["indexed_segments"][1]["empty_segment"] is True
    assert projection["payload"]["indexed_segments"][1]["lines"] == []
    assert projection["payload"]["modality_contract"]["visual_content_supplied"] is False
    lines = projection["line_ledger"]["lines"]
    assert lines[0]["text"].endswith("\r\n") and lines[1]["text"].endswith("\r\n")
    assert lines[-2]["text"].endswith("\u2028")


def test_valid_ranges_derive_exact_unicode_offsets_without_model_math_and_preserve_raw():
    packet, projection = fixture()
    raw = reply(packet, projection)
    before = copy.deepcopy(raw)
    result = m.validate_line_scan(packet, projection, raw)
    assert raw == before and result["raw_line_payload"] == before
    finding = result["payload"]["findings"][0]
    assert finding["start"] == 0 and finding["end"] == len("收入 10\r\n利润 😀\r\n")
    assert finding["quote"] == "收入 10\r\n利润 😀\r\n"
    assert finding["quote"] == packet["segments"][0]["text"][finding["start"] : finding["end"]]
    assert result["passed"] is False
    checked = m.core.validate_scan(packet, result["payload"])
    assert checked["status"] == result["status"]
    assert result["line_mapping_proof"]["earlier_character_response_repair"] is False
    assert result["line_mapping_proof"]["findings"][0]["line_ids"] == ["L000000", "L000001"]
    assert (
        result["payload"]["uncertainties"][0]["segment_id"] == packet["segments"][1]["segment_id"]
    )


@pytest.mark.parametrize(
    "mode",
    [
        "unknown",
        "reversed",
        "cross_segment",
        "empty_segment_line",
        "quoted_response",
        "offset_response",
        "wrong_packet",
        "missing_segment",
        "duplicate_segment",
        "unknown_uncertainty",
        "wrong_metric",
        "duplicate_finding",
    ],
)
def test_invalid_line_protocol_is_rejected_not_repaired(mode):
    packet, projection = fixture()
    raw = reply(packet, projection)
    if mode == "unknown":
        raw["findings"][0]["line_start"] = "L999999"
    elif mode == "reversed":
        raw["findings"][0].update(line_start="L000001", line_end="L000000")
    elif mode == "cross_segment":
        raw["findings"][0]["line_end"] = "L000003"
    elif mode == "empty_segment_line":
        raw["findings"][0]["line_start"] = "S001:L000000"
    elif mode == "quoted_response":
        raw["findings"][0]["quote"] = "income statement"
    elif mode == "offset_response":
        raw["findings"][0]["start"] = 0
    elif mode == "wrong_packet":
        raw["packet_id"] = projection["id"]
    elif mode == "missing_segment":
        raw["segments_reviewed"].remove("S001")
    elif mode == "duplicate_segment":
        raw["segments_reviewed"] = ["S000", "S000", "S002"]
    elif mode == "unknown_uncertainty":
        raw["uncertainties"][0]["segment_key"] = "S999"
    elif mode == "wrong_metric":
        raw["findings"][0]["metric"] = "gross_profit"
    else:
        raw["findings"].append(copy.deepcopy(raw["findings"][0]))
    before = copy.deepcopy(raw)
    with pytest.raises(ValueError):
        m.validate_line_scan(packet, projection, raw)
    assert raw == before


def test_projection_rehash_cannot_hide_removed_original_line():
    packet, projection = fixture()
    projection["line_ledger"]["lines"].pop(1)
    changed = m.base.record(
        m.PROJECTION, **{k: v for k, v in projection.items() if k not in {"id", "schema_version"}}
    )
    with pytest.raises(ValueError, match="complete_original_line_projection"):
        m.validate_projection(packet, changed)


def test_wire_canonical_key_order_cap_transport_and_4096_limit():
    packet, projection = fixture()
    wire = m.render_request(
        packet,
        projection,
        "challenge",
        "registered-model",
        maximum_request_bytes=100000,
        transport_fields=dict(thinking=dict(type="disabled"), stream=False),
    )
    request = json.loads(wire.body)
    assert m.base.encode(request) == wire.body
    assert request["max_tokens"] == 4096 and request["stream"] is False
    assert request["thinking"] == dict(type="disabled")
    assert "Never output character offsets or quote text" in request["messages"][0]["content"]
    assert "you cannot see the other reviewer's output" in request["messages"][0]["content"]
    assert json.loads(request["messages"][1]["content"]) == projection["payload"]
    loaded_packet, loaded_projection = (
        json.loads(m.base.encode(packet)),
        json.loads(m.base.encode(projection)),
    )
    loaded = m.render_request(
        loaded_packet,
        loaded_projection,
        "challenge",
        "registered-model",
        maximum_request_bytes=100000,
        transport_fields=dict(thinking=dict(type="disabled"), stream=False),
    )
    assert (
        loaded.body == wire.body
        and loaded.metadata["request_sha256"] == wire.metadata["request_sha256"]
    )
    with pytest.raises(ValueError, match="no_truncation"):
        m.render_request(
            packet,
            projection,
            "challenge",
            "registered-model",
            maximum_request_bytes=len(wire.body) - 1,
            transport_fields=dict(thinking=dict(type="disabled"), stream=False),
        )
    with pytest.raises(ValueError):
        m.render_request(
            packet,
            projection,
            "challenge",
            "registered-model",
            maximum_request_bytes=100000,
            transport_fields=dict(max_tokens=8192),
        )


def test_no_hard_truncation_of_raw_reason_or_findings():
    packet, projection = fixture()
    raw = reply(packet, projection)
    raw["findings"][0]["reason"] = "具体不确定性。" * 1000
    result = m.validate_line_scan(packet, projection, raw)
    assert result["payload"]["findings"][0]["reasoning"] == raw["findings"][0]["reason"]
    assert result["raw_line_payload"] == raw


def test_schema_example_cannot_pass_as_actual_source_selection():
    packet, projection = fixture()
    example = projection["payload"]["locator_output_contract"]["valid_json_output_example"]
    with pytest.raises(ValueError, match="original_packet_id"):
        m.validate_line_scan(packet, projection, example)
