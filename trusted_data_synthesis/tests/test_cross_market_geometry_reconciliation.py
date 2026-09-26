"""Focused cache derivation checks; no real PDF, source inspection or model calls."""

import copy
import json

import cross_market_geometry_reconciliation_20260926 as m
import pytest


def payload(name="RGB\udc80"):
    return {
        "pages": [{"words": [{"text": "净利润 100"}]}],
        "page_coverage_inventory": [
            {"image_placements": [{"cs-name": name, "bbox": [0, 0, 1, 1]}]}
        ],
    }


def test_colorspace_roundtrip_without_mutating_original_or_financial_words():
    original = payload()
    before = copy.deepcopy(original)
    view = m.represent_payload(original)
    placement = view["page_coverage_inventory"][0]["image_placements"][0]
    assert "cs-name" not in placement
    assert json.loads(placement["cs-name_ascii_json"]) == "RGB\udc80"
    assert view["pages"] == original["pages"]
    assert original == before
    assert m.base.encode(view)


def test_all_colorspace_values_use_the_same_explicit_encoding():
    view = m.represent_payload(payload("RGB中文"))
    assert (
        json.loads(view["page_coverage_inventory"][0]["image_placements"][0]["cs-name_ascii_json"])
        == "RGB中文"
    )


def test_surrogate_in_financial_word_is_not_removed_or_replaced():
    original = payload()
    original["pages"][0]["words"][0]["text"] = "amount\udc80"
    with pytest.raises(UnicodeEncodeError):
        m.represent_payload(original)
    assert original["pages"][0]["words"][0]["text"].endswith("\udc80")


def test_metadata_encoding_collision_rejected():
    original = payload()
    original["page_coverage_inventory"][0]["image_placements"][0]["cs-name_ascii_json"] = (
        "collision"
    )
    with pytest.raises(ValueError, match="encoding_collision"):
        m.represent_payload(original)


def test_output_budget_enforced(monkeypatch):
    monkeypatch.setattr(m, "MAX_RESULT_BYTES", 1)
    with pytest.raises(ValueError, match="output_size"):
        m.represent_payload(payload())


def test_duplicate_source_references_rejected():
    with pytest.raises(ValueError, match="unique_result_keys"):
        m.index_results({"results": [{"path": "/a/key.json"}, {"path": "/b/key.json"}]})


def test_unsettled_cached_derivation_never_repeated(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "RAW", tmp_path)
    monkeypatch.setattr(m.base, "RAW", tmp_path)
    item = {"document": {"raw_object_id": "test"}}
    key = m.base.sha("test")[:24]
    m.save(tmp_path / "attempts" / (key + ".json"), {"attempt": 1})
    monkeypatch.setattr(m, "load_payload", lambda _: pytest.fail("must not rederive"))
    with pytest.raises(ValueError, match="unsettled_derivation_no_retry"):
        m.derive({"id": "test", "maximum_cached_derivations": 440}, item)


def test_source_reference_hash_mismatch_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "ROOT", tmp_path)
    monkeypatch.setattr(m.base, "RAW", tmp_path)
    path = tmp_path / "record.json"
    m.base.write(path, {"original": True})
    reference = m.ref(path)
    reference["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="frozen_evidence_reference"):
        m.read_ref(reference)


def original_fixture():
    original_item = {
        "document": {"raw_object_id": "synthetic"},
        "extraction": {},
        "evidence_audit": {},
        "original_page_text": {},
        "page_selection": {
            "selected_pages": [1],
            "page_count": 1,
            "empty_text_pages_to_render": [],
        },
    }
    value = payload("RGB")
    value["pages"][0]["page_number"] = 1
    value["page_coverage_inventory"][0]["page_number"] = 1
    value.update(
        status="GEOMETRY_COLLECTED_NOT_ADMITTED",
        selected_page_count=1,
        word_count=1,
        original_page_count=1,
        coverage_word_count=1,
        image_placement_count=1,
        blank_page_images=[],
        all_original_blank_pages_rendered=True,
        empty_selected_pages=[],
    )
    original = m.base.record(m.RESULT, **original_item, **value)
    item = dict(
        original_item,
        evidence_route="original_success",
        evidence={"path": "synthetic"},
        original_result={"path": "synthetic"},
    )
    return item, original, value


def test_original_success_is_reused_without_changing_financial_words(monkeypatch):
    item, original, value = original_fixture()
    monkeypatch.setattr(m, "read_ref", lambda _: original)
    result = m.load_payload(item)
    assert result["pages"] == value["pages"]
    assert original["page_coverage_inventory"][0]["image_placements"][0]["cs-name"] == "RGB"


def test_missing_registered_page_rejected_even_if_success_status(monkeypatch):
    item, original, _ = original_fixture()
    body = {k: v for k, v in original.items() if k not in {"schema_version", "id"}}
    body["pages"] = []
    body["selected_page_count"] = 0
    original = m.base.record(m.RESULT, **body)
    monkeypatch.setattr(m, "read_ref", lambda _: original)
    with pytest.raises(ValueError, match="complete_original_page_scope"):
        m.load_payload(item)
