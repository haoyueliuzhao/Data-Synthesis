"""Focused synthetic controls; no registered original PDF opens or outputs."""

import copy
import json
import struct
from types import SimpleNamespace

import cross_market_geometry_capacity_repair_20260926 as m
import pytest


def controls():
    return dict(
        maximum_pages_per_PDF=1200,
        maximum_words_per_page=25000,
        maximum_words_per_PDF=1000000,
        maximum_coverage_words_per_PDF=5000000,
        maximum_image_placements_per_page=100000,
        maximum_image_placements_per_PDF=1000000,
        maximum_result_bytes_per_PDF=512 * 2**20,
        maximum_PNG_bytes_per_page=10 * 2**20,
        render_requested_dpi=120,
        render_maximum_edge_pixels=1800,
    )


def item(count=1, selected=(1,), reused=(), missing=()):
    return dict(
        key="synthetic",
        parent_failure=dict(path="bound", sha256="failed", bytes=1),
        original_item=dict(
            document=dict(path="/never-open-original.pdf", raw_object_id="r"),
            page_selection=dict(
                page_count=count,
                selected_pages=list(selected),
                empty_text_pages_to_render=sorted(
                    [r["page_number"] for r in reused] + list(missing)
                ),
            ),
        ),
        reused_blank_images=list(reused),
        missing_blank_pages=list(missing),
    )


class Page:
    def __init__(self, words=(), images=()):
        self.words, self.images = list(words), list(images)
        self.rect = SimpleNamespace(width=600, height=800)
        self.rotation = 0
        self.word_calls = 0

    def get_text(self, kind, sort):
        assert (kind, sort) == ("words", False)
        self.word_calls += 1
        return self.words

    def get_image_info(self, **kwargs):
        assert kwargs == dict(hashes=False, xrefs=False)
        return self.images

    def get_pixmap(self, **kwargs):
        raise AssertionError("registered surviving image must not be rendered again")


class PDF:
    needs_pass = False

    def __init__(self, pages):
        self.pages = pages
        self.closed = False

    def __len__(self):
        return len(self.pages)

    def __getitem__(self, index):
        return self.pages[index]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.closed = True


def image_info():
    return {
        "bbox": (0, 0, 10, 10),
        "transform": (10, 0, 0, 10, 0, 0),
        "width": 100,
        "height": 100,
        "cs-name": "RGB\udcbd\udcdb",
    }


def test_raised_image_cap_lossless_ASCII_and_one_uniform_word_pass():
    original = item()
    before = copy.deepcopy(original)
    page = Page([(1, 2, 3, 4, "2024", 0, 0, 0)], [image_info()] * 1001)
    pdf = PDF([page])
    opens = []

    def opener(path):
        opens.append(path)
        return pdf

    payload, counts = m.collect(controls(), original, opener, {1: "2024"})
    value = json.loads(payload)
    assert payload.isascii() and b"\\udcbd\\udcdb" in payload
    assert value["page_coverage_inventory"][0]["image_placement_count"] == 1001
    assert (
        value["page_coverage_inventory"][0]["image_placements"][0]["cs-name"] == "RGB\udcbd\udcdb"
    )
    assert len(opens) == 1 and pdf.closed and page.word_calls == 1
    assert counts["image_placements"] == 1001 and counts["geometry_pages"] == 1
    assert original == before


def test_zero_target_document_still_gets_full_coverage_inventory():
    pdf = PDF([Page(), Page()])
    payload, counts = m.collect(controls(), item(2, ()), lambda _: pdf, {1: "a", 2: "b"})
    assert json.loads(payload)["pages"] == []
    assert counts["coverage_pages"] == 2 and counts["geometry_pages"] == 0


@pytest.mark.parametrize("limit", ["page", "document", "words", "bytes"])
def test_fixed_caps_fail_without_truncating_or_refunding(limit):
    plan = controls()
    page = Page([(1, 2, 3, 4, "2024", 0, 0, 0)], [image_info(), image_info()])
    if limit == "page":
        plan["maximum_image_placements_per_page"] = 1
    elif limit == "document":
        plan["maximum_image_placements_per_PDF"] = 1
    elif limit == "words":
        plan["maximum_words_per_page"] = 0
    else:
        plan["maximum_result_bytes_per_PDF"] = 1
    with pytest.raises(ValueError):
        m.collect(plan, item(), lambda _: PDF([page]), {1: "2024"})


def test_exact_reuse_missing_partition_no_automatic_extra_render():
    saved = dict(page_number=1, image=dict(path="bound-original", sha256="hash", bytes=1))
    source = item(2, (1, 2), (saved,), (2,))
    calls = []

    def handler(page, number, plan, original, existing):
        calls.append((number, existing))
        return dict(page_number=number, status="ORIGINAL_BLANK_TEXT_PAGE_RENDERED_NOT_REVIEWED")

    _, counts = m.collect(
        controls(), source, lambda _: PDF([Page(), Page()]), {1: "", 2: ""}, image_handler=handler
    )
    assert calls == [(1, saved), (2, None)]
    assert counts["saved_images"] == 2 and counts["reused_images"] == counts["new_renders"] == 1
    source["missing_blank_pages"] = [1, 2]
    with pytest.raises(ValueError, match="fixed_image_partition"):
        m.collect(controls(), source, lambda _: pytest.fail("must not open"), {1: "", 2: ""})


def test_image_validation_failure_does_not_substitute_render_or_claim_completion():
    saved = dict(page_number=1)

    def handler(*_):
        raise ValueError("reused PNG mismatch")

    with pytest.raises(ValueError, match="reused PNG mismatch"):
        m.collect(
            controls(),
            item(1, (1,), (saved,), ()),
            lambda _: PDF([Page()]),
            {1: ""},
            image_handler=handler,
        )


def roots(monkeypatch, tmp_path):
    monkeypatch.setattr(m.base, "RAW", tmp_path)
    monkeypatch.setattr(m, "PARENT", tmp_path / "original_geometry")
    monkeypatch.setattr(m, "RAW", tmp_path / "capacity_repair")


def PNG_header(width=600, height=800):
    return (
        b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", width, height)
    )


def test_original_PNG_reuse_checks_hash_and_PDF_dimensions_without_rerender(monkeypatch, tmp_path):
    roots(monkeypatch, tmp_path)
    path = m.PARENT / "images/synthetic/page-0001.png"
    path.parent.mkdir(parents=True)
    path.write_bytes(PNG_header())
    original = m.png_inventory(path, 1000) | dict(page_number=1)
    monkeypatch.setattr(
        m,
        "raster_geometry",
        lambda *args: dict(matrix=None, effective_dpi=120, pixel_width=600, pixel_height=800),
    )
    result = m.image_record(Page(), 1, controls(), item(), original)
    assert result["image"] == original["image"]
    assert result["acquisition_mode"] == "REUSED_REGISTERED_ORIGINAL_ORPHAN_PNG_NO_RERENDER"
    path.write_bytes(PNG_header() + b"changed")
    with pytest.raises(ValueError, match="frozen_bytes"):
        m.image_record(Page(), 1, controls(), item(), original)


def test_original_PNG_wrong_dimensions_fail_closed(monkeypatch, tmp_path):
    roots(monkeypatch, tmp_path)
    path = m.PARENT / "images/synthetic/page-0001.png"
    path.parent.mkdir(parents=True)
    path.write_bytes(PNG_header(600, 801))
    original = m.png_inventory(path, 1000) | dict(page_number=1)
    monkeypatch.setattr(
        m,
        "raster_geometry",
        lambda *args: dict(matrix=None, effective_dpi=120, pixel_width=600, pixel_height=800),
    )
    with pytest.raises(ValueError, match="matches_original_PDF_dimensions"):
        m.image_record(Page(), 1, controls(), item(), original)


def test_only_registered_missing_page_can_render(monkeypatch, tmp_path):
    roots(monkeypatch, tmp_path)
    monkeypatch.setattr(
        m,
        "raster_geometry",
        lambda *args: dict(matrix=None, effective_dpi=120, pixel_width=600, pixel_height=800),
    )
    with pytest.raises(ValueError, match="only_fixed_missing_render"):
        m.image_record(Page(), 1, controls(), item(), None)


def test_fifteen_reservations_are_durable_and_unsettled_is_never_reopened(monkeypatch, tmp_path):
    roots(monkeypatch, tmp_path)
    plan = dict(id="synthetic", maximum_original_PDF_opens=15)
    source = item()
    assert m.reserve(plan, source)
    assert not m.reserve(plan, source)
    assert m.document_job(plan, source)["status"] == "UNSETTLED_ATTEMPT_NO_AUTOMATIC_RETRY"
    for i in range(1, 15):
        assert m.reserve(plan, source | dict(key=str(i)))
    with pytest.raises(ValueError, match="attempt_cap"):
        m.reserve(plan, source | dict(key="sixteenth"))


def test_binary_outputs_confined_and_immutable(monkeypatch, tmp_path):
    roots(monkeypatch, tmp_path)
    path = m.RAW / "payloads/synthetic.json"
    first = m.write_bytes(path, b"{}")
    assert m.write_bytes(path, b"{}") == first
    with pytest.raises(ValueError, match="immutable_binary"):
        m.write_bytes(path, b"[]")
    with pytest.raises(ValueError, match="binary_output_root"):
        m.write_bytes(tmp_path / "outside.json", b"{}")


def test_cached_wrapper_requires_intact_new_payload(monkeypatch, tmp_path):
    roots(monkeypatch, tmp_path)
    source, plan = item(), dict(id="synthetic", maximum_result_bytes_per_PDF=1024)
    payload_path = m.RAW / "payloads/synthetic.json"
    reference = m.write_bytes(payload_path, b"{}")
    result = m.base.record(
        m.RESULT,
        protocol_id=plan["id"],
        status=m.SUCCESS,
        original_item=source["original_item"],
        parent_failure=source["parent_failure"],
        payload_file=reference,
        payload_encoding=m.ENCODING,
    )
    path = m.RAW / "documents/synthetic.json"
    m.save(path, result)
    assert m.cached_result(plan, source, path) == result
    payload_path.write_bytes(b"[]")
    with pytest.raises(ValueError, match="cached_payload_integrity"):
        m.cached_result(plan, source, path)


@pytest.mark.parametrize(
    "width,height,rotation",
    [(612, 792, 0), (595.28, 841.89, 90), (2000, 1000, 0), (1000, 2000, 270)],
)
def test_real_PyMuPDF_synthetic_page_dimensions_and_reuse(
    monkeypatch, tmp_path, width, height, rotation
):
    fitz = pytest.importorskip("pymupdf")
    roots(monkeypatch, tmp_path)
    # A newly created in-memory blank PDF, never a registered source file.
    with fitz.open() as pdf:
        page = pdf.new_page(width=width, height=height)
        page.set_rotation(rotation)
        source = item(missing=(1,))
        rendered = m.image_record(page, 1, controls(), source)
        assert rendered["original_PDF_page_dimensions_verified"]
        assert max(rendered["pixel_width"], rendered["pixel_height"]) <= 1801
        original_path = m.PARENT / "images/synthetic/page-0001.png"
        original_path.parent.mkdir(parents=True)
        original_path.write_bytes(
            __import__("pathlib").Path(rendered["image"]["path"]).read_bytes()
        )
        registered = m.png_inventory(original_path, controls()["maximum_PNG_bytes_per_page"])
        monkeypatch.setattr(page, "get_pixmap", lambda **_: pytest.fail("reuse must not render"))
        reused = m.image_record(page, 1, controls(), source, registered)
        assert reused["image"] == registered["image"]
        assert reused["original_PDF_page_dimensions_verified"]
