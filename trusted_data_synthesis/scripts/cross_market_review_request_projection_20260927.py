"""Lossless text-locator projection of frozen source-review packets.

The source packet is immutable and remains the response-validation authority.
Only bulky geometry inventory details are omitted from the model-facing view;
their content hash, page identity, alerts and image counts remain explicit.
No file I/O, provider call, experiment registration or semantic approval occurs.
"""

import copy
from dataclasses import dataclass

import cross_market_source_review_20260926 as core

base = core.base
SCRIPT = "trusted_data_synthesis/scripts/cross_market_review_request_projection_20260927.py"
PROJECTION = "cross_market_review_text_request_projection"
POLICY = "complete_frozen_segments_and_intervals_text_only.v1"
PACKET_FIELDS = {
    "schema_version",
    "id",
    "raw_object_id",
    "raw_sha256",
    "original_url",
    "page_text_reference",
    "segments",
    "metric_universe",
    "independent_of_Student_and_Q",
    "registered_candidate_intervals",
    "geometry_reference",
    "page_coverage",
    "full_original_document_page_count",
}
SEGMENT_FIELDS = {
    "raw_object_id",
    "page",
    "page_text_sha256",
    "page_characters",
    "start",
    "end",
    "text",
    "segment_id",
}


def require(condition, reason):
    base.require(condition, "review_projection." + reason)


def source_identity(packet, reference):
    base.checked(packet, "cross_market_source_review_packet")
    require(set(packet) == PACKET_FIELDS, "unrecognized_source_packet_schema_not_silently_dropped")
    payload = base.encode(packet)
    require(
        reference["sha256"] == base.sha(payload)
        and reference["bytes"] == len(payload)
        and isinstance(reference.get("path"), str)
        and bool(reference["path"]),
        "exact_registered_source_packet_bytes",
    )
    require(
        packet["metric_universe"] == list(core.METRICS)
        and packet["independent_of_Student_and_Q"] is True,
        "same_four_metrics_and_no_Student_conditioning",
    )
    require(
        type(packet["full_original_document_page_count"]) is int
        and packet["full_original_document_page_count"] > 0,
        "original_document_page_count",
    )
    segments = packet["segments"]
    require(isinstance(segments, list) and bool(segments), "source_segments_present")
    identifiers = set()
    for segment in segments:
        require(set(segment) == SEGMENT_FIELDS, "source_segment_schema")
        body = {k: v for k, v in segment.items() if k != "segment_id"}
        require(
            segment["segment_id"] == "source_segment:" + base.sha(base.encode(body))
            and segment["segment_id"] not in identifiers,
            "source_segment_hash_and_uniqueness",
        )
        identifiers.add(segment["segment_id"])
        require(
            segment["raw_object_id"] == packet["raw_object_id"]
            and type(segment["page"]) is int
            and 1 <= segment["page"] <= packet["full_original_document_page_count"]
            and all(type(segment[k]) is int for k in ("start", "end", "page_characters"))
            and 0 <= segment["start"] <= segment["end"] <= segment["page_characters"]
            and isinstance(segment["text"], str)
            and len(segment["text"]) == segment["end"] - segment["start"],
            "source_segment_original_page_and_character_offsets",
        )
    require(isinstance(packet["registered_candidate_intervals"], list), "complete_interval_list")
    coverage = packet["page_coverage"]
    require(
        isinstance(coverage, list)
        and len(coverage) == len({r["page_number"] for r in coverage})
        and {r["page_number"] for r in coverage} == {s["page"] for s in segments},
        "same_source_packet_page_coverage",
    )
    return payload


def page_projection(row):
    inventory = row["original_geometry_inventory"]
    require(isinstance(row["quality_alerts"], list), "original_page_alerts")
    if inventory is not None:
        require(inventory["page_number"] == row["page_number"], "inventory_page_identity")
    return dict(
        page_number=row["page_number"],
        original_geometry_inventory_sha256=base.sha(base.encode(inventory))
        if inventory is not None
        else None,
        original_geometry_inventory_present=inventory is not None,
        saved_text_empty=inventory.get("saved_text_empty") if inventory is not None else None,
        image_placement_count=inventory.get("image_placement_count")
        if inventory is not None
        else None,
        quality_alerts=copy.deepcopy(row["quality_alerts"]),
        image_placement_details_omitted_from_text_request=True,
        original_visual_and_vector_content_not_reviewed_by_this_projection=True,
    )


def output_contract(source_packet_id):
    """An expressly synthetic valid-JSON example, never invented real locators."""
    return dict(
        packet_id_must_equal=source_packet_id,
        segments_reviewed_must_list_every_exact_supplied_segment_id=True,
        offset_basis="Python Unicode code points in the exact segment.text; "
        "start inclusive, end exclusive; not UTF-8 bytes or UTF-16 code units",
        exact_quote_rule="quote must equal segment.text[start:end] with no normalization, "
        "trimming, translation or reformatting",
        finding_periods_are_untrusted_proposals_not_financial_certificates=True,
        no_response_correction_or_semantic_soft_pass=True,
        example_notice="SCHEMA EXAMPLE ONLY. Synthetic text is 示例; 示例[0:1] is 示. "
        "The EXAMPLE_ONLY identifiers below are NOT real packet/segment IDs. Never copy them; "
        "use this request's packet_id and supplied segment_ids. The example is not a finding "
        "about any original source.",
        valid_json_output_example=dict(
            packet_id="EXAMPLE_ONLY_NOT_A_REAL_PACKET_ID",
            segments_reviewed=["EXAMPLE_ONLY_NOT_A_REAL_SEGMENT_ID"],
            findings=[
                dict(
                    finding_id="example-finding-1",
                    segment_id="EXAMPLE_ONLY_NOT_A_REAL_SEGMENT_ID",
                    start=0,
                    end=1,
                    quote="示",
                    metric_id="unknown",
                    classification="uncertain",
                    period_start=None,
                    period_end=None,
                    reasoning="Synthetic schema illustration only; actual findings require "
                    "original-source evidence.",
                )
            ],
            uncertainties=[],
        ),
    )


def project_packet(packet, packet_reference):
    """Return a new content-addressed record, never reuse the source packet ID."""
    original_bytes = source_identity(packet, packet_reference)
    view = dict(
        packet_id=packet["id"],
        source_packet_id=packet["id"],
        source_packet_sha256=base.sha(original_bytes),
        source_packet_reference=copy.deepcopy(packet_reference),
        raw_object_id=packet["raw_object_id"],
        raw_sha256=packet["raw_sha256"],
        original_url=packet["original_url"],
        page_text_reference=copy.deepcopy(packet["page_text_reference"]),
        geometry_reference=copy.deepcopy(packet["geometry_reference"]),
        full_original_document_page_count=packet["full_original_document_page_count"],
        segments=copy.deepcopy(packet["segments"]),
        metric_universe=copy.deepcopy(packet["metric_universe"]),
        registered_candidate_intervals=copy.deepcopy(packet["registered_candidate_intervals"]),
        independent_of_Student_and_Q=True,
        page_coverage=[page_projection(row) for row in packet["page_coverage"]],
        modality_contract=dict(
            material_kind="complete_saved_text_segments_only",
            visual_content_supplied=False,
            visual_semantic_review_completed=False,
            all_original_pages_semantically_reviewed=False,
            nonempty_text_does_not_prove_visual_coverage=True,
            one_packet_projection_does_not_certify_full_document_coverage=True,
            source_exhaustion_certificate_created=False,
            geometry_details_remain_in_original_hashed_packet=True,
        ),
        locator_output_contract=output_contract(packet["id"]),
    )
    return base.record(
        PROJECTION,
        policy=POLICY,
        source_packet_id=packet["id"],
        source_packet_reference=copy.deepcopy(packet_reference),
        source_packet_sha256=base.sha(original_bytes),
        source_segment_ids=[s["segment_id"] for s in packet["segments"]],
        source_segments_sha256=base.sha(base.encode(packet["segments"])),
        source_intervals_sha256=base.sha(base.encode(packet["registered_candidate_intervals"])),
        source_packet_bytes=len(original_bytes),
        projected_payload_bytes=len(base.encode(view)),
        payload=view,
        text_and_intervals_unchanged=True,
        API_calls=0,
        source_exhaustion_certified=False,
    )


def validate_projection(packet, projection):
    base.checked(projection, PROJECTION)
    expected = project_packet(packet, projection["source_packet_reference"])
    require(projection == expected, "projection_not_exact_registered_field_projection")
    return projection


@dataclass(frozen=True)
class FrozenRequest:
    body: bytes
    metadata: dict


def render_request(
    packet, projection, lane, model, *, maximum_request_bytes, transport_fields=None
):
    """Cap the final exact UTF-8 HTTP body, including approved transport fields.

    The future transport must send body verbatim; appending/re-serializing fields
    after this function would not be the capped, hashed request returned here.
    """
    validate_projection(packet, projection)
    require(
        type(maximum_request_bytes) is int and maximum_request_bytes > 0,
        "explicit_positive_request_byte_cap",
    )
    require(isinstance(model, str) and bool(model), "explicit_model_identity")
    fields = copy.deepcopy(transport_fields or {})
    require(
        set(fields) <= {"thinking", "stream"}, "transport_cannot_override_frozen_prompt_or_model"
    )
    require(
        "thinking" not in fields or fields["thinking"] == {"type": "disabled"},
        "only_explicit_disabled_thinking_wire_option",
    )
    require("stream" not in fields or fields["stream"] is False, "only_nonstreaming_wire_option")
    request = core.request_payload(projection["payload"], lane, model)
    # The frozen helper's json.dumps preserves dict insertion order inside this
    # string. Canonicalize that one JSON value too: file readback must not alter
    # the exact wire hash while the projection's content identity stays equal.
    request["messages"][1]["content"] = base.encode(projection["payload"]).decode("utf-8")
    request.update(fields)
    require(request["max_tokens"] == core.MAX_OUTPUT_TOKENS == 4096, "frozen_output_token_cap")
    body = base.encode(request)
    require(len(body) <= maximum_request_bytes, "request_byte_cap_exceeded_no_truncation")
    return FrozenRequest(
        body=body,
        metadata=dict(
            policy=POLICY,
            projection_id=projection["id"],
            source_packet_id=packet["id"],
            source_packet_sha256=projection["source_packet_sha256"],
            lane=lane,
            model=model,
            request_sha256=base.sha(body),
            request_bytes=len(body),
            maximum_request_bytes=maximum_request_bytes,
            maximum_output_tokens=4096,
            transport_fields=fields,
            body_encoding="canonical_UTF8_JSON",
            text_only=True,
            source_exhaustion_certified=False,
        ),
    )


def validate_projected_scan(packet, projection, response):
    """Never repair provider JSON, offsets, quotes, IDs or semantic assertions."""
    validate_projection(packet, projection)
    return core.validate_scan(packet, response)
