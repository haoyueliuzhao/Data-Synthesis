"""Synthetic cache-only recovery; no original financial files, PDFs or models."""

import copy
import json
import struct

import cross_market_geometry_encoding_recovery_20260926 as m
import pytest


def payload():
    return dict(
        status="GEOMETRY_COLLECTED_NOT_ADMITTED",
        pages=[
            dict(
                page_number=1,
                width=600,
                height=800,
                rotation=0,
                words=[dict(x0=1, y0=2, x1=3, y1=4, text="2024", block=0, line=0, word=0)],
                reading_order=[0],
                reading_order_is_only_geometric_not_semantic=True,
            )
        ],
        selected_page_count=1,
        word_count=1,
        original_page_count=1,
        page_coverage_inventory=[
            dict(
                page_number=1,
                width=600,
                height=800,
                rotation=0,
                extracted_word_count=1,
                saved_text_character_count=4,
                saved_text_empty=False,
                image_placement_count=1,
                image_placements=[
                    {
                        "bbox": [0, 0, 10, 10],
                        "transform": [10, 0, 0, 10, 0, 0],
                        "cs-name": "RGB\udcbd\udcdb",
                    }
                ],
                image_semantics_reviewed=False,
                vector_semantics_reviewed=False,
            )
        ],
        coverage_word_count=1,
        image_placement_count=1,
        blank_page_images=[],
        all_original_blank_pages_rendered=True,
        empty_selected_pages=[],
    )


def error_repr(value):
    source = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return error_for_text(source)


def error_for_text(source):
    try:
        source.encode("utf-8")
    except UnicodeEncodeError as error:
        return repr(error)
    raise AssertionError("synthetic fixture has no surrogate")


def geometry():
    return dict(
        maximum_pages_per_PDF=1200,
        maximum_words_per_page=25000,
        maximum_words_per_PDF=1000000,
        maximum_coverage_words_per_PDF=5000000,
        maximum_image_placements_per_page=1000,
        maximum_image_placements_per_PDF=20000,
        maximum_PNG_bytes_per_page=10 * 2**20,
        render_maximum_edge_pixels=1800,
        render_requested_dpi=120,
    )


def item():
    return dict(
        key="synthetic",
        original_item=dict(
            document=dict(path="/unread-original.pdf", raw_object_id="synthetic"),
            page_selection=dict(page_count=1, selected_pages=[1], empty_text_pages_to_render=[]),
        ),
    )


def test_exact_exception_and_ascii_payload_are_lossless():
    value = payload()
    decoded = m.decode_error(error_repr(value))
    encoded, counts = m.validate_payload(decoded, item(), geometry())
    assert json.loads(encoded) == value and encoded.isascii()
    assert b"\\udcbd\\udcdb" in encoded
    assert counts["surrogate_fields"] == 1 and counts["surrogate_characters"] == 2
    assert value["pages"][0]["words"][0]["text"] == "2024"


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os').system('true')",
        "UnicodeEncodeError('utf-8', str('x'), 0, 1, 'surrogates not allowed')",
        "UnicodeEncodeError(*('utf-8', 'x', 0, 1, 'surrogates not allowed'))",
        "UnicodeEncodeError('utf-8','x',0,1,reason='surrogates not allowed')",
        "('utf-8', 'x', 0, 1, 'surrogates not allowed')",
    ],
)
def test_AST_only_allows_five_literal_constants(expression):
    with pytest.raises(ValueError, match="AST_constant_allowlist"):
        m.decode_error(expression)


def test_oversized_error_rejected_before_AST():
    with pytest.raises(ValueError, match="error_bound"):
        m.decode_error("x" * (m.MAX_ERROR_CHARS + 1))


def test_embedded_noncanonical_JSON_is_not_silently_rewritten():
    source = json.dumps(payload(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    with pytest.raises(ValueError, match="canonical_embedded_JSON"):
        m.decode_error(error_for_text(source + " "))


def test_forged_error_position_rejected():
    value = repr(UnicodeEncodeError("utf-8", "abc\udcbd", 0, 1, "surrogates not allowed"))
    with pytest.raises(ValueError, match="reproduced_exception"):
        m.decode_error(value)


def test_surrogate_in_financial_word_or_key_is_not_permitted():
    value = payload()
    value["pages"][0]["words"][0]["text"] = "12\udcbd"
    with pytest.raises(ValueError, match="outside_image_colorspace"):
        m.validate_payload(value, item(), geometry())
    value = payload()
    value["bad\udcbd"] = 1
    with pytest.raises(ValueError, match="surrogate_in_key"):
        m.surrogate_inventory(value)


@pytest.mark.parametrize(
    "mutation", ["geometry_page", "coverage_page", "word_count", "reviewed", "cap"]
)
def test_page_identity_counts_caps_and_unreviewed_status_are_preserved(mutation):
    value = payload()
    if mutation == "geometry_page":
        value["pages"][0]["page_number"] = 2
    elif mutation == "coverage_page":
        value["page_coverage_inventory"][0]["page_number"] = 2
    elif mutation == "word_count":
        value["word_count"] = 2
    elif mutation == "reviewed":
        value["page_coverage_inventory"][0]["image_semantics_reviewed"] = True
    else:
        value["page_coverage_inventory"][0]["extracted_word_count"] = 25001
    with pytest.raises(ValueError):
        m.validate_payload(value, item(), geometry())


def setup_roots(monkeypatch, tmp_path):
    monkeypatch.setattr(m.base, "RAW", tmp_path)
    monkeypatch.setattr(m, "PARENT", tmp_path / "geometry")
    monkeypatch.setattr(m, "RAW", tmp_path / "encoding_recovery")


def test_PNG_reference_dimensions_hash_and_bound_path(monkeypatch, tmp_path):
    setup_roots(monkeypatch, tmp_path)
    path = m.PARENT / "images/synthetic/page-0001.png"
    header = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", 600, 800)
    # This fixture only supplies the bounded PNG header inspected by this helper.
    path.parent.mkdir(parents=True)
    path.write_bytes(header)
    image = dict(
        image=m.ref(path),
        pixel_width=600,
        pixel_height=800,
        requested_dpi=120,
        effective_dpi=120,
        status="ORIGINAL_BLANK_TEXT_PAGE_RENDERED_NOT_REVIEWED",
        OCR_performed=False,
    )
    m.verify_PNG(image, "synthetic", 1, geometry())
    wrong = copy.deepcopy(image)
    wrong["pixel_width"] = 599
    with pytest.raises(ValueError, match="dimensions"):
        m.verify_PNG(wrong, "synthetic", 1, geometry())
    wrong = copy.deepcopy(image)
    wrong["image"]["sha256"] = "changed"
    with pytest.raises(ValueError, match="PNG_reference"):
        m.verify_PNG(wrong, "synthetic", 1, geometry())
    with pytest.raises(ValueError, match="PNG_reference"):
        m.verify_PNG(image, "different-document", 1, geometry())


def test_cache_recovery_writes_new_wrapper_without_changing_failed_parent(monkeypatch, tmp_path):
    setup_roots(monkeypatch, tmp_path)
    source = item()
    failure = m.base.record(
        "cross_market_original_PDF_geometry",
        status="GEOMETRY_ACQUISITION_FAILED",
        error=error_repr(payload()),
        **source["original_item"],
    )
    failure_path = m.PARENT / "documents/synthetic.json"
    m.base.write(failure_path, failure)
    source["failure"] = m.ref(failure_path)
    original = failure_path.read_bytes()
    plan = dict(id="synthetic-plan", maximum_cached_attempts=4)
    result = m.recover_one(plan, source, geometry())
    assert result["status"] == "LOSSLESS_CACHED_PAYLOAD_PRESERVED_NOT_ADMITTED"
    assert result["schema_version"].endswith(m.RESULT)
    assert result["PDF_opens"] == 0 and not result["downstream_authorized"]
    assert not result["geometry_complete"] and result["original_failure_unchanged"]
    assert failure_path.read_bytes() == original
    assert m.base.read(result["payload_file"]["path"]) == payload()
    assert m.recover_one(plan, source, geometry()) == result
    assert len(list((m.RAW / "attempts").glob("*.json"))) == 1


def test_durable_attempts_are_not_refunded_and_missing_output_not_retried(monkeypatch, tmp_path):
    setup_roots(monkeypatch, tmp_path)
    plan = dict(id="synthetic-plan", maximum_cached_attempts=1)
    source = item() | dict(failure=dict(path="never-read", sha256="bound", bytes=1))
    assert m.reserve(plan, source)
    assert not m.reserve(plan, source)
    assert (
        m.recover_one(plan, source, geometry())["status"]
        == "UNSETTLED_CACHE_ATTEMPT_NO_AUTOMATIC_RETRY"
    )
    with pytest.raises(ValueError, match="attempt_cap"):
        m.reserve(plan, source | dict(key="another"))


def test_payload_file_is_immutable_and_confined(monkeypatch, tmp_path):
    setup_roots(monkeypatch, tmp_path)
    path = m.RAW / "payloads/synthetic.json"
    first = m.write_payload(path, b'{"value":1}')
    assert m.write_payload(path, b'{"value":1}') == first
    with pytest.raises(ValueError, match="immutable_payload"):
        m.write_payload(path, b'{"value":2}')
    with pytest.raises(ValueError, match="output_root"):
        m.write_payload(tmp_path / "outside.json", b"{}")


@pytest.mark.parametrize("corruption", ["missing", "size", "hash"])
def test_successful_reuse_requires_payload_integrity(monkeypatch, tmp_path, corruption):
    setup_roots(monkeypatch, tmp_path)
    source = item() | dict(failure=dict(path="bound-failure", sha256="hash", bytes=1))
    plan = dict(id="synthetic-plan")
    path = m.RAW / "payloads/synthetic.json"
    reference = m.write_payload(path, b'{"value":1}')
    value = dict(
        protocol_id=plan["id"],
        failure=source["failure"],
        original_item=source["original_item"],
        status="LOSSLESS_CACHED_PAYLOAD_PRESERVED_NOT_ADMITTED",
        payload_file=reference,
        payload_encoding=m.ENCODING,
    )
    m.verify_cached_result(plan, source, value)
    if corruption == "missing":
        path.unlink()
    elif corruption == "size":
        path.write_bytes(b"{}")
    else:
        path.write_bytes(b'{"value":2}')
    with pytest.raises(ValueError, match="cached_payload_integrity"):
        m.verify_cached_result(plan, source, value)
