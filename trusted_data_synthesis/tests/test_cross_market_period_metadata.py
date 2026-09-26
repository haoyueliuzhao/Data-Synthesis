"""Pure metadata repair tests; no real PDFs, models or network."""

import copy
import pickle

import pytest
import repair_cross_market_period_metadata_20260926 as m
from finraw.cn_financial_statements import _report_year


def inventory():
    return {
        "roster": [
            {
                "documents": [
                    {
                        "year": 2023,
                        "raw_object_id": "original",
                        "metadata": {"year": "2023", "source_id": "hkex_disclosures"},
                    }
                ]
            }
        ]
    }


def test_repair_passes_the_original_year_to_existing_parser_without_mutating_parent():
    parent = inventory()
    before = copy.deepcopy(parent)
    assert _report_year(parent["roster"][0]["documents"][0]["metadata"]) is None
    result = m.corrected_inventory(parent)
    assert parent == before
    doc = result["roster"][0]["documents"][0]
    assert _report_year(doc["metadata"]) == 2023
    del doc["metadata"]["record_period_hint"]
    assert result == parent


def test_repair_applies_to_CN_and_HK_not_just_empty_HK_results():
    parent = inventory()
    parent["roster"][0]["documents"].append(
        {"year": 2024, "metadata": {"year": "2024", "source_id": "cninfo_announcements"}}
    )
    result = m.corrected_inventory(parent)
    assert [_report_year(d["metadata"]) for d in result["roster"][0]["documents"]] == [2023, 2024]


def test_inconsistent_or_preexisting_period_binding_rejected():
    parent = inventory()
    parent["roster"][0]["documents"][0]["metadata"]["year"] = "2022"
    with pytest.raises(ValueError, match="same_original_manifest_year"):
        m.corrected_inventory(parent)
    parent = inventory()
    parent["roster"][0]["documents"][0]["metadata"]["record_period_hint"] = "2023"
    with pytest.raises(ValueError, match="only_missing_key_repaired"):
        m.corrected_inventory(parent)


def test_isolated_helpers_keep_old_RAW_and_preserve_spawn_pickling(tmp_path, monkeypatch):
    old = m.base.RAW
    monkeypatch.setattr(m, "RAW", tmp_path / "revision")
    monkeypatch.setattr(m, "_namespace", None)
    helpers = m.helpers()
    assert helpers.RAW == tmp_path / "revision"
    assert m.base.RAW == old
    helpers.write(m.RAW / "test.json", {"ok": True})
    assert m.base.read(m.RAW / "test.json") == {"ok": True}
    assert helpers.run.__globals__["document_job"] is m.document_job
    assert pickle.loads(pickle.dumps(m.document_job)) is m.document_job
