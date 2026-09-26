"""Synthetic complete-text projection and wire-byte controls; no provider calls."""

import copy
import json

import cross_market_review_request_projection_20260927 as m
import pytest


def fixture():
    pages = [dict(page=1, text="甲😀乙 e\u0301\nRevenue 10\n"), dict(page=2, text="")]
    inventory = [
        dict(
            page_number=p["page"],
            saved_text_empty=not p["text"],
            image_placement_count=1000 if p["page"] == 1 else 1,
            image_placements=[
                dict(number=i, bbox=[0, 0, 600, 800], cs_name="DeviceRGB") for i in range(1000)
            ],
            image_semantics_reviewed=False,
            vector_semantics_reviewed=False,
        )
        for p in pages
    ]
    intervals = [
        dict(
            task_id="task:" + str(i),
            metric_id=m.core.METRICS[i % 4],
            periods=[
                ["2021-01-01", "2021-12-31"],
                ["2022-01-01", "2022-12-31"],
                ["2023-01-01", "2023-12-31"],
            ],
        )
        for i in range(35)
    ]
    packet = m.core.build_packets(
        dict(
            raw_object_id="raw:1",
            sha256="a" * 64,
            original_url="https://official.example/report.pdf",
        ),
        dict(path="/frozen/text.json", sha256="b" * 64, bytes=100),
        pages,
        geometry=dict(page_coverage_inventory=inventory),
        geometry_reference=dict(path="/frozen/geometry.json", sha256="c" * 64, bytes=999),
        task_intervals=intervals,
    )[0]
    return packet, reference(packet)


def reference(packet):
    payload = m.base.encode(packet)
    return dict(path="/frozen/packet.json", sha256=m.base.sha(payload), bytes=len(payload))


def rehash(record, kind):
    return m.base.record(
        kind, **{k: v for k, v in record.items() if k not in {"id", "schema_version"}}
    )


def response(packet):
    first = packet["segments"][0]
    return dict(
        packet_id=packet["id"],
        segments_reviewed=[s["segment_id"] for s in packet["segments"]],
        findings=[
            dict(
                finding_id="finding:1",
                segment_id=first["segment_id"],
                start=1,
                end=2,
                quote="😀",
                metric_id="unknown",
                classification="uncertain",
                period_start=None,
                period_end=None,
                reasoning="Original text locator only.",
            )
        ],
        uncertainties=[],
    )


def test_projection_preserves_every_segment_interval_and_source_identity_without_mutation():
    packet, ref = fixture()
    before = copy.deepcopy(packet)
    projected = m.project_packet(packet, ref)
    assert packet == before
    assert projected["payload"]["segments"] == packet["segments"]
    assert (
        projected["payload"]["registered_candidate_intervals"]
        == packet["registered_candidate_intervals"]
    )
    assert len(projected["payload"]["registered_candidate_intervals"]) == 35
    assert projected["payload"]["metric_universe"] == list(m.core.METRICS)
    assert projected["id"] != packet["id"]
    assert projected["payload"]["packet_id"] == packet["id"]
    assert projected["source_packet_sha256"] == ref["sha256"]
    assert m.project_packet(packet, ref) == projected


def test_geometry_details_omitted_but_hash_alerts_images_and_blank_page_retained():
    packet, ref = fixture()
    projected = m.project_packet(packet, ref)
    assert projected["projected_payload_bytes"] < projected["source_packet_bytes"]
    for old, new in zip(
        packet["page_coverage"], projected["payload"]["page_coverage"], strict=True
    ):
        assert "original_geometry_inventory" not in new
        assert "image_placements" not in new
        assert new["original_geometry_inventory_sha256"] == m.base.sha(
            m.base.encode(old["original_geometry_inventory"])
        )
        assert new["quality_alerts"] == old["quality_alerts"]
        assert (
            new["image_placement_count"]
            == old["original_geometry_inventory"]["image_placement_count"]
        )
    assert projected["payload"]["segments"][1]["text"] == ""
    assert projected["payload"]["page_coverage"][1]["saved_text_empty"] is True
    assert projected["payload"]["modality_contract"]["visual_content_supplied"] is False
    assert (
        projected["payload"]["modality_contract"]["all_original_pages_semantically_reviewed"]
        is False
    )


def test_exact_frozen_prompt_and_final_wire_body_hash_including_transport_fields():
    packet, ref = fixture()
    projected = m.project_packet(packet, ref)
    result = m.render_request(
        packet,
        projected,
        "challenge",
        "registered-model",
        maximum_request_bytes=100000,
        transport_fields=dict(thinking=dict(type="disabled"), stream=False),
    )
    request = json.loads(result.body)
    original = m.core.request_payload(packet, "challenge", "registered-model")
    assert request["messages"][0] == original["messages"][0]
    assert json.loads(request["messages"][1]["content"]) == projected["payload"]
    assert request["response_format"] == dict(type="json_object")
    assert request["max_tokens"] == 4096
    assert request["thinking"] == dict(type="disabled") and request["stream"] is False
    assert m.base.encode(request) == result.body
    assert result.metadata["request_sha256"] == m.base.sha(result.body)
    assert result.metadata["request_bytes"] == len(result.body)


def test_UTF8_byte_cap_exact_boundary_and_no_truncation():
    packet, ref = fixture()
    projected = m.project_packet(packet, ref)
    result = m.render_request(packet, projected, "discovery", "model", maximum_request_bytes=100000)
    size = len(result.body)
    assert size > len(result.body.decode("utf-8"))
    assert (
        m.render_request(packet, projected, "discovery", "model", maximum_request_bytes=size).body
        == result.body
    )
    with pytest.raises(ValueError, match="cap_exceeded_no_truncation"):
        m.render_request(packet, projected, "discovery", "model", maximum_request_bytes=size - 1)
    assert projected["payload"]["segments"] == packet["segments"]


def test_inner_and_outer_request_hash_invariant_to_JSON_key_order_and_file_readback():
    packet, ref = fixture()
    projection = m.project_packet(packet, ref)
    loaded_packet = json.loads(m.base.encode(packet))
    loaded_projection = json.loads(m.base.encode(projection))
    rebuilt_projection = m.project_packet(loaded_packet, ref)
    assert projection["id"] == loaded_projection["id"] == rebuilt_projection["id"]
    requests = [
        m.render_request(p, view, "discovery", "model", maximum_request_bytes=100000)
        for p, view in (
            (packet, projection),
            (loaded_packet, loaded_projection),
            (loaded_packet, rebuilt_projection),
        )
    ]
    assert all(r.body == requests[0].body for r in requests)
    assert all(
        r.metadata["request_sha256"] == requests[0].metadata["request_sha256"] for r in requests
    )
    user_content = json.loads(requests[0].body)["messages"][1]["content"]
    assert user_content == m.base.encode(projection["payload"]).decode("utf-8")


@pytest.mark.parametrize("cap", [0, -1, True, "100000"])
def test_explicit_positive_integer_request_cap_required(cap):
    packet, ref = fixture()
    with pytest.raises(ValueError, match="positive_request_byte_cap"):
        m.render_request(
            packet, m.project_packet(packet, ref), "discovery", "model", maximum_request_bytes=cap
        )


@pytest.mark.parametrize(
    "fields",
    [
        dict(messages=[]),
        dict(max_tokens=8192),
        dict(model="other"),
        dict(stream=True),
        dict(thinking=dict(type="enabled")),
    ],
)
def test_transport_fields_cannot_override_contract(fields):
    packet, ref = fixture()
    with pytest.raises(ValueError):
        m.render_request(
            packet,
            m.project_packet(packet, ref),
            "discovery",
            "model",
            maximum_request_bytes=100000,
            transport_fields=fields,
        )


@pytest.mark.parametrize("field", ["segments", "registered_candidate_intervals", "page_coverage"])
def test_validly_rehashed_projection_tampering_still_rejected_against_original(field):
    packet, ref = fixture()
    projected = m.project_packet(packet, ref)
    projected["payload"][field].pop()
    altered = rehash(projected, m.PROJECTION)
    with pytest.raises(ValueError, match="exact_registered_field_projection"):
        m.validate_projection(packet, altered)


def test_bad_original_reference_and_unknown_source_fields_not_silently_accepted():
    packet, ref = fixture()
    ref["bytes"] -= 1
    with pytest.raises(ValueError, match="source_packet_bytes"):
        m.project_packet(packet, ref)
    packet["new_undeclared_private_field"] = "must not silently drop or send"
    altered = rehash(packet, "cross_market_source_review_packet")
    with pytest.raises(ValueError, match="unrecognized_source_packet_schema"):
        m.project_packet(altered, reference(altered))


def test_source_segment_hash_and_duplicate_ids_fail_even_with_new_packet_hash():
    packet, _ = fixture()
    packet["segments"].append(copy.deepcopy(packet["segments"][0]))
    altered = rehash(packet, "cross_market_source_review_packet")
    with pytest.raises(ValueError, match="segment_hash_and_uniqueness"):
        m.project_packet(altered, reference(altered))


def test_response_is_checked_against_original_unicode_source_without_offset_or_ID_correction():
    packet, ref = fixture()
    projected = m.project_packet(packet, ref)
    value = response(packet)
    result = m.validate_projected_scan(packet, projected, value)
    assert result == m.core.validate_scan(packet, value)
    assert result["passed"] is False
    value["findings"][0]["end"] = 3  # UTF-16-style end would include an extra code point.
    with pytest.raises(ValueError, match="exact_source_quote"):
        m.validate_projected_scan(packet, projected, value)
    value = response(packet)
    value["packet_id"] = projected["id"]
    with pytest.raises(ValueError, match="scan_packet"):
        m.validate_projected_scan(packet, projected, value)


def test_schema_example_uses_no_fake_real_source_ids_and_cannot_pass_as_result():
    packet, ref = fixture()
    projected = m.project_packet(packet, ref)
    contract = projected["payload"]["locator_output_contract"]
    example = json.loads(json.dumps(contract["valid_json_output_example"], ensure_ascii=False))
    assert "SCHEMA EXAMPLE ONLY" in contract["example_notice"]
    assert "Python Unicode code points" in contract["offset_basis"]
    assert example["packet_id"].startswith("EXAMPLE_ONLY_")
    assert example["findings"][0]["segment_id"].startswith("EXAMPLE_ONLY_")
    with pytest.raises(ValueError, match="scan_packet"):
        m.validate_projected_scan(packet, projected, example)
