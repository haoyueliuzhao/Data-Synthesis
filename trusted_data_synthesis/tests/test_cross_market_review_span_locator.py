"""Synthetic prospective span semantics; no previous-reply repair or API calls."""

import copy
import json

import cross_market_review_span_locator_20260927 as m
import pytest


def rehash_packet(packet):
    return m.base.record(
        "cross_market_source_review_packet",
        **{k: v for k, v in packet.items() if k not in {"id", "schema_version"}},
    )


def freeze(packet):
    raw = m.base.encode(packet)
    ref = dict(path="/frozen/packet.json", sha256=m.base.sha(raw), bytes=len(raw))
    return packet, m.project_packet(packet, ref)


def packet_from_pages(pages):
    return m.core.build_packets(
        dict(
            raw_object_id="raw",
            sha256="a" * 64,
            original_url="https://official.example/original.pdf",
        ),
        dict(path="/frozen/text.json", sha256="b" * 64, bytes=100),
        pages,
        task_intervals=[
            dict(
                task_id="t",
                metric_id="revenue",
                periods=[
                    ["2021-01-01", "2021-12-31"],
                    ["2022-01-01", "2022-12-31"],
                    ["2023-01-01", "2023-12-31"],
                ],
            )
        ],
    )[0]


def multi_page():
    return freeze(
        packet_from_pages(
            [
                dict(page=1, text="甲😀\r\n乙\n"),
                dict(page=2, text=""),
                dict(page=3, text="丙\n丁\n"),
            ]
        )
    )


def overlap(ranges=((0, 9), (3, 12)), corrupt=False):
    text = "aa\nbb\ncc\ndd\n"
    packet = packet_from_pages([dict(page=1, text=text)])
    segments = []
    for i, (start, end) in enumerate(ranges):
        body = dict(
            raw_object_id="raw",
            page=1,
            page_text_sha256=m.base.sha(text),
            page_characters=len(text),
            start=start,
            end=end,
            text=text[start:end],
        )
        if corrupt and i == 1:
            body["text"] = "X" + body["text"][1:]
        body["segment_id"] = "source_segment:" + m.base.sha(m.base.encode(body))
        segments.append(body)
    packet["segments"] = segments
    return freeze(rehash_packet(packet))


def raw_reply(packet, projection, a=None, b=None):
    lines = projection["line_ledger"]["lines"]
    return dict(
        packet_id=packet["id"],
        segments_reviewed=[s["segment_key"] for s in projection["line_ledger"]["segments"]],
        findings=[
            dict(
                id="f1",
                boundary_a=a or lines[0]["line_id"],
                boundary_b=b or lines[-1]["line_id"],
                metric="revenue",
                kind="uncertain",
                period_start=None,
                period_end=None,
                reason="Original source interval requires independent adjudication.",
            )
        ],
        uncertainties=[],
    )


def test_cross_page_envelope_includes_empty_page_without_fabricating_quote():
    packet, projection = multi_page()
    raw = raw_reply(packet, projection, "L000001", "L000002")
    before = copy.deepcopy(raw)
    result = m.validate_span_scan(packet, projection, raw)
    assert raw == before and result["raw_span_payload"] == before
    assert [f["quote"] for f in result["payload"]["findings"]] == ["乙\n", "丙\n"]
    group = result["span_mapping_proof"]["range_groups"][0]
    assert [p["page"] for p in group["page_coverage"]] == [1, 2, 3]
    assert group["page_coverage"][1]["empty_segment_lineage"]
    assert group["page_coverage"][1]["unique_original_characters"] == 0
    assert group["unique_original_characters"] == 4
    assert group["financial_observation_count"] is None
    assert result["passed"] is False
    assert m.core.validate_scan(packet, result["payload"])["passed"] is False


def test_unordered_boundaries_sort_by_original_position_not_global_line_ID():
    packet, projection = overlap()
    # L2 is cc in S0 at page offset6; L3 is bb in S1 at offset3.
    raw = raw_reply(packet, projection, "L000002", "L000003")
    result = m.validate_span_scan(packet, projection, raw)
    reverse = copy.deepcopy(raw)
    reverse["findings"][0].update(boundary_a="L000003", boundary_b="L000002")
    other = m.validate_span_scan(packet, projection, reverse)
    group = result["span_mapping_proof"]["range_groups"][0]
    mirrored = other["span_mapping_proof"]["range_groups"][0]
    assert group["canonical_boundary_line_ids"] == ["L000003", "L000002"]
    assert group["canonical_range"]["start"] == dict(page=1, offset=3)
    assert group["canonical_range"]["end"] == dict(page=1, offset=9)
    assert group["range_group_id"] == mirrored["range_group_id"]
    assert result["payload"] == other["payload"]
    assert group["original_proposal"] != mirrored["original_proposal"]


def test_overlap_lineage_and_union_not_double_counted_as_observations():
    packet, projection = overlap(((0, 9), (3, 12), (6, 12)))
    result = m.validate_span_scan(packet, projection, raw_reply(packet, projection))
    proof = result["span_mapping_proof"]
    group = proof["range_groups"][0]
    assert len(group["fragments"]) == 3 and len(group["overlap_lineage"]) == 3
    assert group["unique_original_characters"] == 12
    assert group["represented_fragment_characters"] == 24
    assert group["duplicate_overlap_characters"] == 12
    assert sum(x["characters"] for x in group["overlap_lineage"]) == 15
    assert (
        sum(
            r["end"] - r["start"]
            for f in group["fragments"]
            for r in f["canonical_owned_page_intervals"]
        )
        == 12
    )
    assert proof["raw_locator_group_count"] == 1 and proof["derived_quote_fragment_count"] == 3
    assert proof["financial_observation_count"] is None
    assert all(
        f["evidence_fragment_not_financial_observation"] for f in result["payload"]["findings"]
    )


def test_repeated_proposals_preserved_but_global_character_union_deduplicated():
    packet, projection = overlap()
    raw = raw_reply(packet, projection)
    second = copy.deepcopy(raw["findings"][0])
    second["id"] = "f2"
    raw["findings"].append(second)
    proof = m.validate_span_scan(packet, projection, raw)["span_mapping_proof"]
    assert proof["raw_locator_group_count"] == 2 and proof["derived_quote_fragment_count"] == 4
    assert proof["distinct_original_source_envelopes"] == 1
    assert proof["deduplicated_source_characters_across_groups"] == 12


@pytest.mark.parametrize("failure", ["gap", "conflicting_overlap", "missing_page"])
def test_unprovided_or_inconsistent_source_span_rejected(failure):
    if failure == "gap":
        packet, projection = overlap(((0, 3), (6, 12)))
    elif failure == "conflicting_overlap":
        packet, projection = overlap(corrupt=True)
    else:
        packet, _ = multi_page()
        packet["segments"] = [s for s in packet["segments"] if s["page"] != 2]
        packet["page_coverage"] = [p for p in packet["page_coverage"] if p["page_number"] != 2]
        packet, projection = freeze(rehash_packet(packet))
    with pytest.raises(ValueError):
        m.validate_span_scan(packet, projection, raw_reply(packet, projection))


@pytest.mark.parametrize(
    "failure",
    [
        "unknown",
        "old_start_end",
        "quote",
        "missing_segment",
        "multiline_reason",
        "wrong_metric",
        "duplicate_id",
        "multiline_uncertainty",
    ],
)
def test_prospective_contract_does_not_fix_old_or_invalid_responses(failure):
    packet, projection = multi_page()
    raw = raw_reply(packet, projection)
    if failure == "unknown":
        raw["findings"][0]["boundary_a"] = "L999999"
    elif failure == "old_start_end":
        raw["findings"][0]["line_start"] = raw["findings"][0].pop("boundary_a")
        raw["findings"][0]["line_end"] = raw["findings"][0].pop("boundary_b")
    elif failure == "quote":
        raw["findings"][0]["quote"] = "made-up"
    elif failure == "missing_segment":
        raw["segments_reviewed"].pop()
    elif failure == "multiline_reason":
        raw["findings"][0]["reason"] = "one\ntwo"
    elif failure == "wrong_metric":
        raw["findings"][0]["metric"] = "gross_profit"
    elif failure == "duplicate_id":
        raw["findings"].append(copy.deepcopy(raw["findings"][0]))
    else:
        raw["uncertainties"] = [dict(segment_key="S001", reason="one\ntwo")]
    before = copy.deepcopy(raw)
    with pytest.raises(ValueError):
        m.validate_span_scan(packet, projection, raw)
    assert raw == before


def test_input_and_wire_lossless_canonical_and_explicit_cap():
    packet, projection = multi_page()
    before = copy.deepcopy(packet)
    assert projection["original_segments"] == packet["segments"]
    assert (
        projection["payload"]["registered_candidate_intervals"]
        == packet["registered_candidate_intervals"]
    )
    for source, indexed in zip(
        packet["segments"], projection["payload"]["indexed_segments"], strict=True
    ):
        assert "".join(r["text"] for r in indexed["lines"]) == source["text"]
    options = dict(thinking=dict(type="disabled"), stream=False)
    wire = m.render_request(
        packet,
        projection,
        "challenge",
        "model",
        maximum_request_bytes=100000,
        transport_fields=options,
    )
    request = json.loads(wire.body)
    assert m.base.encode(request) == wire.body and request["max_tokens"] == 4096
    assert "UNORDERED" in request["messages"][0]["content"]
    loaded = m.render_request(
        json.loads(m.base.encode(packet)),
        json.loads(m.base.encode(projection)),
        "challenge",
        "model",
        maximum_request_bytes=100000,
        transport_fields=options,
    )
    assert loaded.body == wire.body
    with pytest.raises(ValueError, match="no_truncation"):
        m.render_request(
            packet,
            projection,
            "challenge",
            "model",
            maximum_request_bytes=len(wire.body) - 1,
            transport_fields=options,
        )
    assert packet == before


def test_same_endpoint_is_one_line_not_rejected_as_reversal():
    packet, projection = multi_page()
    raw = raw_reply(packet, projection, "L000000", "L000000")
    result = m.validate_span_scan(packet, projection, raw)
    assert result["payload"]["findings"][0]["quote"] == "甲😀\r\n"


def test_rehashed_projection_mutation_rejected():
    packet, projection = multi_page()
    projection["line_ledger"]["lines"][0]["page_start"] += 1
    altered = m.base.record(
        m.PROJECTION, **{k: v for k, v in projection.items() if k not in {"id", "schema_version"}}
    )
    with pytest.raises(ValueError, match="original_span_projection"):
        m.validate_projection(packet, altered)
