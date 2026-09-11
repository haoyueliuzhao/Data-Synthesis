"""Read-only governance controls; no downloads, generated scoring or model execution."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_basis_scale_preparation import governance as g

ROOT = Path(__file__).resolve().parents[2]


def entry(company="A", year=2005, page=1, number=1, *, table=None, text="original source"):
    filename = f"{company}/{year}/page_{page}.pdf"
    return {
        "id": filename + f"-{number}",
        "filename": filename,
        "table": table if table is not None else [["metric", str(year)], ["amount", company]],
        "pre_text": [text],
        "post_text": [],
        "qa": {"question": "fixture question"},
    }


def write(root, relative, value, *, raw=False):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    data = value if raw else json.dumps(value).encode()
    path.write_bytes(data)
    return path


def known(registered=(), reviewed=()):
    return {
        "id": "fixture_known_exposure",
        "exposure_layers": {
            "registered": g._blacklist(registered),
            "source_reviewed": g._blacklist(reviewed),
            "union": g._blacklist([*registered, *reviewed]),
        },
    }


def fixture_archive(tmp_path, monkeypatch):
    a, b, c = entry("A"), entry("B"), entry("C")
    path = write(tmp_path, g.ARCHIVE, [a, b, c])
    monkeypatch.setattr(g, "ARCHIVE_SHA256", hashlib.sha256(path.read_bytes()).hexdigest())
    registered_path = "trusted_data_synthesis/artifacts/fixture/old/preparation/registrations.json"
    write(
        tmp_path, registered_path, [{"task_id": a["id"]}, {"task_id": a["id"] + "::clarified.v2"}]
    )
    write(
        tmp_path,
        g.SOURCE_DISPOSITIONS,
        (
            "PAGE_DISPOSITIONS = " + repr({b["filename"]: ("fixture", "source-only review")}) + "\n"
        ).encode(),
        raw=True,
    )
    write(tmp_path, g.DIFFICULTY_REJECTED, [{"qa_id": c["id"], "reason": "source rejected"}])
    write(tmp_path, g.CENSUS, {"questions": 3, "scope": "metadata inspected"})
    return a, b, c, registered_path


def test_known_exposure_keeps_registered_and_source_only_layers(tmp_path, monkeypatch):
    a, b, c, reference = fixture_archive(tmp_path, monkeypatch)
    result = g.known_exposure(tmp_path)
    assert result["registered_question_ids"] == [a["id"]]
    assert result["source_reviewed_question_ids"] == [b["id"], c["id"]]
    assert result["registered_id_count"] == 1
    assert result["registered_id_references"][a["id"]] == [reference]
    assert result["whole_snapshot_metadata_previously_inspected"]
    assert result["metadata_inspection_not_all_tasks_previously_evaluated"]
    assert g.BIDIRECTIONAL in result["missing_supplemental_inputs"]
    assert g.PQ_PANEL in result["missing_supplemental_inputs"]
    for ref in result["source_references"]:
        raw = (tmp_path / ref["path"]).read_bytes()
        assert len(raw) == ref["bytes"] and hashlib.sha256(raw).hexdigest() == ref["sha256"]
    assert (
        result["certified_new_tasks"] == result["Provider_calls"] == result["tokenizer_calls"] == 0
    )


def test_current_intake_or_future_public_preparation_is_not_historical(tmp_path, monkeypatch):
    a, b, c, _ = fixture_archive(tmp_path, monkeypatch)
    write(tmp_path, g.NEW_OUTPUT + "new/preparation/registrations.json", [{"task_id": b["id"]}])
    write(tmp_path, g.NEW_OUTPUT + "source_inventory_20260911/source_intake/finqa/train.json", [c])
    result = g.known_exposure(tmp_path)
    assert result["registered_question_ids"] == [a["id"]]
    assert not any(path.startswith(g.NEW_OUTPUT) for path in result["scanned_registered_files"])


def test_historical_archive_byte_change_is_rejected(tmp_path, monkeypatch):
    fixture_archive(tmp_path, monkeypatch)
    path = tmp_path / g.ARCHIVE
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="exact_historical_benchmark_snapshot"):
        g.known_exposure(tmp_path)


def test_repository_inventory_reproduces_saved_registered_exposure_lower_bound():
    result = g.known_exposure(ROOT)
    assert result["archive_reference"]["sha256"] == g.ARCHIVE_SHA256
    assert result["archive_rows"] == 1147
    assert result["registered_id_count"] == 73
    assert len(result["exposure_layers"]["registered"]["company_proxies"]) == 32
    assert len(result["exposure_layers"]["union"]["question_ids"]) == 140
    assert len(result["exposure_layers"]["union"]["company_proxies"]) == 43
    assert result["missing_supplemental_inputs"] == []
    assert result["company_exclusion_is_scenario_not_audit_mandate"]


def test_known_exact_page_excludes_different_question_on_that_page():
    original = entry()
    other_question = entry(number=2, table=[["different source projection"]])
    result = g.annotated_governance([other_question], [], known([original]))
    row = result["rows"][0]
    assert "historical_registered_page" in row["historical_exact_exposure_reasons"]
    assert "historical_registered_question" not in row["historical_exact_exposure_reasons"]
    assert row["fresh_source_status"] == "EXCLUDE_KNOWN_SOURCE"


def test_same_company_different_source_is_only_strict_scenario_excluded():
    old, new = entry(), entry(year=2010, page=9, text="different source")
    row = g.annotated_governance([new], [], known([old]))["rows"][0]
    assert row["fresh_source_lead"]
    assert row["historical_company_proxy_exposed"]
    assert not row["strict_fresh_company_scenario_eligible"]
    assert row["strict_fresh_company_scenario_reasons"] == ["historical_company_proxy"]
    assert not row["task_certified"] and not row["dual_sufficiency_certified"]


def test_actual_DG_repeated_table_across_report_years_is_detected():
    data = json.loads((ROOT / g.ARCHIVE).read_bytes())
    earlier = next(e for e in data if e["id"] == "DG/2005/page_44.pdf-2")
    later = next(e for e in data if e["id"] == "DG/2007/page_67.pdf-1")
    result = g.annotated_governance([later], [earlier], known([earlier]))
    assert later["filename"] != earlier["filename"]
    assert (
        result["rows"][0]["table_sha256"]
        == "6867f27547f7a76161306dac6e6e9ee3a3536aab1ff3c27ca08b248d99db7797"
    )
    assert "historical_registered_table" in result["rows"][0]["historical_exact_exposure_reasons"]
    assert result["overlap"]["table"] and result["cross_population_source_collision"]
    draft = g.draft_company_split([earlier, later])
    assert len(draft["components"]) == 1
    assert len({r["draft_split"] for r in draft["rows"]}) == 1


def test_context_match_is_retained_separately_from_table_and_page():
    first = entry("A", text="shared exact public source")
    second = entry("B", page=8, table=first["table"], text="shared exact public source")
    result = g.annotated_governance([first], [second], known())
    assert not result["overlap"]["page"]
    assert result["overlap"]["context_sha256"]
    assert result["status"] == "SOURCE_GAP_NO_TRAINING_SOURCE_LEADS"
    assert result["real_company_disjoint_certified"] is False


def test_alias_UA_UAA_is_conservative_not_entity_certification():
    older, newer = entry("UAA"), entry("UA", year=2011)
    result = g.annotated_governance([newer], [older], known([older]))
    assert (
        result["rows"][0]["company_proxy_group"]
        == result["evaluation_rows"][0]["company_proxy_group"]
    )
    assert result["overlap"]["company_proxy_group"]
    assert result["rows"][0]["historical_company_proxy_exposed"]
    assert result["alias_evidence_status"] == "CONSERVATIVE_GROUPING_NOT_ENTITY_CERTIFICATION"
    assert not result["real_company_disjoint_certified"]
    assert len(g.draft_company_split([older, newer])["components"]) == 1


def test_caller_aliases_are_transitive_and_never_certified_without_entity_review():
    rows = [entry("FORMER"), entry("LATER"), entry("CURRENT")]
    aliases = {"FORMER": "LATER", "LATER": {"canonical": "CURRENT", "verified": True}}
    draft = g.draft_company_split(rows, aliases=aliases)
    assert len(draft["components"]) == 1
    assert not draft["real_company_disjoint_certified"]


def test_duplicate_table_joins_different_company_proxy_groups():
    table = [["same original disclosure", "2005"], ["total", "123"]]
    rows = [entry("A", table=table), entry("B", table=table, text="different surroundings")]
    draft = g.draft_company_split(rows)
    assert len(draft["components"]) == 1
    assert draft["components"][0]["raw_company_codes"] == ["A", "B"]
    assert len({r["draft_split"] for r in draft["rows"]}) == 1


def test_metadata_and_private_answers_do_not_change_source_equivalence_or_split():
    first = entry()
    second = copy.deepcopy(first)
    second.update(
        source_split="new_official_train", source_file_sha256="new hash", source_record_index=99
    )
    second["qa"] = {"question": "new wording", "program": "private program", "exe_ans": 42}
    result = g.annotated_governance([first], [second], known())
    left, right = result["rows"][0], result["evaluation_rows"][0]
    for key in ("page", "table_sha256", "context_sha256"):
        assert left[key] == right[key]
    assert right["provenance"]["source_record_index"] == 99
    assert (
        g.draft_company_split([first])["rows"][0]["draft_split"]
        == g.draft_company_split([second])["rows"][0]["draft_split"]
    )


def test_fixed_split_draft_is_order_independent_and_makes_no_task_quota_claim():
    rows = [entry(f"C{i}", year=2005 + i) for i in range(20)]
    a, b = g.draft_company_split(rows), g.draft_company_split(list(reversed(rows)))
    assert a == b
    assert a["seed"] == g.SPLIT_SEED and a["seed_search_attempts"] == 0
    assert a["fixed_split_weights"] == {"train": 10, "dev": 9, "confirm": 36}
    assert a["status"] == "DRAFT_NOT_TASK_CERTIFIED" and a["certified_new_tasks"] == 0
    assert not a["generated_quality_used"] and a["model_calls"] == 0


def test_empty_inputs_are_explicit_source_leads_not_fake_certified_tasks():
    result = g.annotated_governance([], [], known())
    assert result["population_counts"] == {"rows": 0, "evaluation_rows": 0}
    assert result["certified_new_tasks"] == 0
    assert not result["real_company_disjoint_certified"]
    assert g.draft_company_split([])["components"] == []


@pytest.mark.parametrize("alias", [{"": "A"}, {"A": None}, {"A": {"verified": True}}])
def test_unresolved_alias_shape_does_not_silently_create_company_identity(alias):
    with pytest.raises(ValueError, match="alias_shape"):
        g.draft_company_split([entry()], aliases=alias)


def test_evaluation_only_same_source_is_excluded_from_training_after_redownload():
    old = entry("A")
    downloaded = copy.deepcopy(old)
    downloaded.update(source_split="new_official_train", source_record_index=621)
    report = g.annotated_governance([downloaded], [old], known())
    row = report["rows"][0]
    assert row["training_source_excluded"]
    assert set(row["training_source_exclusion_reasons"]) == {
        "evaluation_only_question",
        "evaluation_only_page",
        "evaluation_only_table",
        "evaluation_only_context",
    }
    assert not row["fresh_evaluation_source_excluded"]
    assert not report["support_generation_allowed"] and not report["training_allowed"]


def test_historical_non_evaluation_only_source_has_separate_freshness_flag():
    old = entry("A")
    evaluation = entry("B", year=2008, page=99)
    row = g.annotated_governance([old], [evaluation], known([old]))["rows"][0]
    assert not row["training_source_excluded"]
    assert row["fresh_evaluation_source_excluded"]
    assert "historical_registered_page" in row["fresh_evaluation_source_exclusion_reasons"]


def test_company_overlap_alone_does_not_fail_all_downloaded_training_sources():
    evaluation = entry("A")
    new_source = entry("A", year=2018, page=88, text="different original disclosure")
    report = g.annotated_governance([new_source], [evaluation], known())
    assert report["company_proxy_overlap_observed"]
    assert not report["cross_population_source_collision"]
    assert not report["rows"][0]["training_source_excluded"]
    assert report["status"] == "SOURCE_LEADS_NOT_TASK_CERTIFIED"
    assert not report["real_company_disjoint_certified"]


def test_split_draft_preserves_evaluation_only_blacklist_without_launch_authority():
    original = entry()
    draft = g.draft_company_split([original], evaluation_rows=[original])
    assert draft["rows"][0]["training_source_excluded"]
    assert draft["source_eligibility_not_overridden_by_hash"]
    assert not draft["support_generation_allowed"] and not draft["training_allowed"]
