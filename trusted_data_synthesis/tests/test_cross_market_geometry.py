"""Synthetic geometry/budget controls: no production PDF opens or finance facts."""

import copy
from pathlib import Path
from types import SimpleNamespace

import cross_market_geometry_20260926 as m
import pytest


def parsed():
    return dict(
        candidates=[
            dict(
                page_number=10,
                _period_source_page=4,
                _unit_source_page=10,
                _statement_source_page=4,
                candidate_state="rejected",
                extraction_metadata=dict(period_source_page=4),
            )
        ],
        tables=[dict(page_number=18)],
    )


def test_every_candidate_table_and_source_anchor_selected_without_admission_filter():
    value = parsed()
    original = copy.deepcopy(value)
    result = m.page_selection(value, 30)
    assert result["anchor_pages"] == [4, 10, 18]
    assert result["selected_pages"] == list(range(1, 23))
    assert result["candidates_filtered_by_prior_admission"] is False
    assert value == original


def test_empty_text_pages_selected_without_neighbor_expansion():
    result = m.page_selection({}, 30, [20, 20])
    assert result["selected_pages"] == result["empty_text_pages_to_render"] == [20]
    assert result["anchor_pages"] == []


@pytest.mark.parametrize("page", [0, 31, True, "2", 2.5])
def test_invalid_anchor_fails_instead_of_clamping_or_metadata_repair(page):
    with pytest.raises(ValueError, match="anchor_page"):
        m.page_selection(dict(candidates=[dict(page_number=page)]), 30)


class Page:
    def __init__(self, words=(), images=()):
        self.words, self.images = list(words), list(images)
        self.rect = SimpleNamespace(width=600, height=800)
        self.rotation = 0
        self.calls = []

    def get_text(self, kind, sort=False):
        self.calls.append((kind, sort))
        assert (kind, sort) == ("words", False)
        return self.words

    def get_image_info(self, **kwargs):
        assert kwargs == dict(hashes=False, xrefs=False)
        return self.images


def word(text="2024", x=200, y=100, block=0, line=0, index=0):
    return (x, y, x + 30, y + 12, text, block, line, index)


def test_geometry_preserves_stream_boxes_and_adds_only_index_order():
    page = Page([word("bottom", y=200), word("top", y=20, block=1)])
    result = m.geometry_page(page, 9, 10)
    assert [w["text"] for w in result["words"]] == ["bottom", "top"]
    assert result["reading_order"] == [1, 0]
    assert result["words"][1]["block"] == 1
    assert result["page_number"] == 9
    assert result["reading_order_is_only_geometric_not_semantic"]


def test_word_cap_never_truncates_or_reports_success():
    with pytest.raises(ValueError, match="page_word_cap"):
        m.geometry_page(Page([word(), word()]), 1, 1)


def test_nonfinite_boxes_fail():
    with pytest.raises(ValueError, match="word_values"):
        m.geometry_page(Page([word(x=float("nan"))]), 1, 1)


class PDF:
    needs_pass = False

    def __init__(self, pages):
        self.pages = pages
        self.exited = False

    def __len__(self):
        return len(self.pages)

    def __getitem__(self, index):
        return self.pages[index]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.exited = True


def controls():
    return dict(
        maximum_pages_per_PDF=1200,
        maximum_words_per_page=100,
        maximum_words_per_PDF=1000,
        maximum_coverage_words_per_PDF=1000,
        maximum_image_placements_per_page=100,
        maximum_image_placements_per_PDF=1000,
        maximum_result_bytes_per_PDF=2**20,
    )


def item(page_count=3, selected=(2,), empty=()):
    return dict(
        document=dict(path="not-opened.pdf", raw_object_id="r"),
        page_selection=dict(
            page_count=page_count,
            selected_pages=list(selected),
            empty_text_pages_to_render=list(empty),
        ),
    )


def test_one_open_full_inventory_selected_geometry_and_no_double_word_calls():
    pdf = PDF([Page([word()]) for _ in range(3)])
    opens = []

    def opener(path):
        opens.append(path)
        return pdf

    result = m.extract_geometry(controls(), item(), opener, saved_pages={1: "a", 2: "b", 3: "c"})
    assert opens == [Path("not-opened.pdf")] and pdf.exited
    assert [p["page_number"] for p in result["pages"]] == [2]
    assert [p["page_number"] for p in result["page_coverage_inventory"]] == [1, 2, 3]
    assert all(p.calls == [("words", False)] for p in pdf.pages)
    assert result["coverage_word_count"] == 3 and result["word_count"] == 1


def test_zero_anchor_pdf_still_opened_and_all_pages_inventoried():
    pdf = PDF([Page()])
    result = m.extract_geometry(controls(), item(1, ()), lambda _: pdf, saved_pages={1: "text"})
    assert result["pages"] == [] and len(result["page_coverage_inventory"]) == 1


def test_render_failure_preserves_geometry_and_explicit_unresolved_evidence():
    pdf = PDF([Page()])

    def renderer(*_):
        raise ValueError("image too large")

    result = m.extract_geometry(
        controls(), item(1, (1,), (1,)), lambda _: pdf, renderer=renderer, saved_pages={1: ""}
    )
    assert result["status"] == "GEOMETRY_COLLECTED_NOT_ADMITTED"
    assert not result["all_original_blank_pages_rendered"]
    assert result["blank_page_images"][0]["status"] == "BLANK_PAGE_RENDER_FAILED_UNRESOLVED"
    assert result["page_coverage_inventory"][0]["saved_text_empty"]


def test_nonempty_text_page_image_is_inventoried_not_claimed_reviewed():
    image = dict(
        number=3,
        bbox=(0, 10, 100, 100),
        transform=(100, 0, 0, 90, 0, 10),
        width=400,
        height=300,
        size=22000,
    )
    result = m.page_coverage(Page([word()], [image]), 1, [word()], "has text", controls())
    assert result["image_placements"][0]["bbox"] == [0, 10, 100, 100]
    assert result["image_placement_count"] == 1
    assert not result["image_semantics_reviewed"] and not result["vector_semantics_reviewed"]


def test_page_count_disagreement_fails_before_extraction():
    pdf = PDF([Page()])
    with pytest.raises(ValueError, match="page_count_or_encryption"):
        m.extract_geometry(controls(), item(2), lambda _: pdf, saved_pages={1: ""})
    assert pdf.pages[0].calls == []


def output_root(monkeypatch, tmp_path):
    monkeypatch.setattr(m, "RAW", tmp_path / "geometry")
    monkeypatch.setattr(m.base, "RAW", tmp_path)


def test_attempt_reservation_is_durable_and_never_refunded(monkeypatch, tmp_path):
    output_root(monkeypatch, tmp_path)
    plan = dict(id="plan", maximum_original_PDF_opens=1)
    assert m.reserve(plan, "k", dict(raw_object_id="r"))
    assert not m.reserve(plan, "k", dict(raw_object_id="r"))
    with pytest.raises(ValueError, match="attempt_cap"):
        m.reserve(plan, "k2", dict(raw_object_id="r2"))


def test_reserved_missing_document_is_not_opened_again(monkeypatch, tmp_path):
    output_root(monkeypatch, tmp_path)
    plan = dict(id="plan", maximum_original_PDF_opens=1)
    source = item()
    key = m.key_for(source["document"])
    m.reserve(plan, key, source["document"])
    assert m.document_job(plan, source)["status"] == "UNSETTLED_ATTEMPT_NO_AUTOMATIC_RETRY"


def test_image_save_is_immutable_and_confined(monkeypatch, tmp_path):
    output_root(monkeypatch, tmp_path)
    path = m.RAW / "images/test.png"
    first = m.save_PNG(path, b"synthetic-PNG-placeholder")
    assert m.save_PNG(path, b"synthetic-PNG-placeholder") == first
    with pytest.raises(ValueError, match="immutable_image_conflict"):
        m.save_PNG(path, b"different")
    with pytest.raises(ValueError, match="image_output_root"):
        m.save_PNG(tmp_path / "outside.png", b"x")


def test_umbrella_binding_requires_exact_original_bytes_and_budget():
    documents = [
        dict(
            document=dict(
                raw_object_id=str(i), sha256=f"hash{i}", bytes=1, path=f"/original/{i}.pdf"
            )
        )
        for i in range(440)
    ]
    umbrella = dict(
        fixed_original_documents=[row["document"] for row in documents],
        maximum_additional_PDF_open_attempts=440,
        maximum_attempts_per_PDF=1,
        maximum_CPU_workers=8,
        maximum_pages_per_PDF=1200,
        maximum_full_page_image_inventory=104439,
        maximum_empty_page_renders=420,
        evaluation_authorized=False,
    )
    m.bind_umbrella(umbrella, documents)
    bad = copy.deepcopy(umbrella)
    bad["fixed_original_documents"][3]["sha256"] = "replacement"
    with pytest.raises(ValueError, match="same_umbrella_sources_and_budgets"):
        m.bind_umbrella(bad, documents)
    bad = copy.deepcopy(umbrella)
    bad["maximum_empty_page_renders"] = 421
    with pytest.raises(ValueError, match="same_umbrella_sources_and_budgets"):
        m.bind_umbrella(bad, documents)
