"""Bounded local issuer-evidence controls, without downloads or model execution."""

import hashlib
import json

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_basis_scale_preparation import entity


def snapshot(
    root,
    cik=1,
    *,
    date="2026-07-22",
    name="Fixture Corp",
    tickers=("AAA",),
    payload_cik=None,
    former=None,
):
    path = root / entity.SUBMISSIONS / f"cik={cik:010d}" / f"snapshot_date={date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    value = {
        "cik": str(cik).zfill(10) if payload_cik is None else payload_cik,
        "name": name,
        "tickers": list(tickers),
        "formerNames": former or [],
    }
    path.write_bytes(json.dumps(value).encode())
    return path


def pointer(value, path):
    for key in path.strip("/").split("/"):
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def test_unique_ticker_has_exact_file_hash_and_json_pointer_evidence(tmp_path):
    path = snapshot(tmp_path, payload_cik=1, tickers=("AAA", "BBB"))
    result = entity.runtime(tmp_path, ["BBB"])
    row = result["evidence_by_ticker"]["BBB"]
    assert row["status"] == "UNIQUE_STORED_SUBMISSION_ASSOCIATION"
    assert row["verified_current_submission_association"]
    assert not row["historical_report_company_identity_certified"]
    match = row["matches"][0]
    raw = path.read_bytes()
    value = json.loads(raw)
    assert match["source_reference"]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert match["source_reference"]["bytes"] == len(raw)
    assert pointer(value, match["ticker_json_pointer"]) == match["ticker_original_value"] == "BBB"
    assert pointer(value, match["cik_json_pointer"]) == match["cik_original_value"] == 1
    assert pointer(value, match["name_json_pointer"]) == match["name"]
    assert match["cik"] == "0000000001"
    assert result["historical_company_identity_certified_count"] == 0
    assert not result["real_company_disjoint_certified"]


def test_preferred_date_does_not_resurrect_a_ticker_from_older_snapshot(tmp_path):
    snapshot(tmp_path, date="2026-07-08", tickers=("OLD",))
    snapshot(tmp_path, date="2026-07-22", tickers=("NEW",))
    result = entity.runtime(tmp_path, ["OLD", "NEW"])
    assert result["selected_snapshot_count"] == 1
    assert result["selected_snapshot_date_counts"] == {"2026-07-22": 1}
    assert result["evidence_by_ticker"]["OLD"]["status"] == "UNMATCHED_IN_USABLE_LOCAL_SNAPSHOTS"
    assert result["evidence_by_ticker"]["NEW"]["verified_current_submission_association"]
    assert result["snapshots"][0]["available_older_dates_not_read"] == ["2026-07-08"]
    assert all("2026-07-22" in ref["path"] for ref in result["source_references"])


def test_older_date_fallback_is_explicit_when_preferred_file_is_absent(tmp_path):
    snapshot(tmp_path, date="2026-07-08")
    result = entity.runtime(tmp_path, ["AAA"])
    assert result["selected_snapshot_date_counts"] == {"2026-07-08": 1}
    assert result["snapshots"][0]["fallback_because_preferred_snapshot_absent"]
    row = result["rows"][0]
    assert row["verified_current_submission_association"]
    assert row["current_means_chosen_stored_snapshot_not_today"]
    assert row["historical_report_company_identity_status"] == "UNRESOLVED"


def test_invalid_preferred_snapshot_does_not_silently_fall_back(tmp_path):
    snapshot(tmp_path, date="2026-07-08")
    snapshot(tmp_path, date="2026-07-22", payload_cik="0000000009")
    result = entity.runtime(tmp_path, ["AAA"])
    assert result["usable_snapshot_count"] == 0
    assert result["snapshots"][0]["status"] == "UNUSABLE_STORED_SUBMISSION"
    assert result["snapshots"][0]["reason"] == "entity.directory_and_payload_cik_mismatch"
    assert not result["rows"][0]["verified_current_submission_association"]


def test_ticker_shared_by_multiple_ciks_stays_ambiguous(tmp_path):
    snapshot(tmp_path, 1, name="Issuer One")
    snapshot(tmp_path, 2, name="Issuer Two")
    result = entity.runtime(tmp_path, ["AAA"])
    row = result["rows"][0]
    assert row["status"] == "AMBIGUOUS_MULTIPLE_CIKS"
    assert row["matched_ciks"] == ["0000000001", "0000000002"]
    assert not row["verified_current_submission_association"]
    assert len(row["matches"]) == 2


def test_same_issuer_name_never_merges_distinct_ciks(tmp_path):
    snapshot(tmp_path, 1, name="Same Corp", tickers=("AAA",))
    snapshot(tmp_path, 2, name=" same  corp ", tickers=("BBB",))
    result = entity.runtime(tmp_path, ["AAA", "BBB"])
    assert result["same_normalized_name_multiple_ciks"] == {
        "same corp": ["0000000001", "0000000002"]
    }
    assert result["rows"][0]["matched_ciks"] != result["rows"][1]["matched_ciks"]
    assert all(row["verified_current_submission_association"] for row in result["rows"])
    assert all(row["matches"][0]["same_normalized_name_other_ciks"] for row in result["rows"])
    assert not result["real_company_disjoint_certified"]


def test_former_name_is_preserved_but_never_used_to_infer_historical_ticker(tmp_path):
    snapshot(
        tmp_path,
        tickers=("NEW",),
        former=[
            {
                "name": "OLD",
                "from": "2000-01-01",
                "to": "2010-01-01",
            }
        ],
    )
    result = entity.runtime(tmp_path, ["OLD"])
    assert result["rows"][0]["status"] == "UNMATCHED_IN_USABLE_LOCAL_SNAPSHOTS"
    assert result["snapshots"][0]["former_names"][0]["json_pointer"] == "/formerNames/0"
    assert result["snapshots"][0]["former_names_not_a_historical_report_binding"]


def test_UA_UAA_cik_evidence_remains_separate_from_conservative_alias_policy(tmp_path):
    snapshot(tmp_path, 1336917, name="Under Armour Fixture", tickers=("UA", "UAA"))
    result = entity.runtime(tmp_path, ["UA", "UAA"])
    alias = result["conservative_alias_check"]
    assert alias["shared_stored_cik_evidence"] == ["0001336917"]
    assert alias["current_shared_cik_observed"]
    assert not alias["historical_report_alias_identity_certified"]
    assert not result["real_company_disjoint_certified"]


def test_missing_UA_UAA_metadata_does_not_become_cik_evidence(tmp_path):
    snapshot(tmp_path, tickers=("AAA",))
    result = entity.runtime(tmp_path, ["UA", "UAA"])
    assert result["conservative_alias_check"]["shared_stored_cik_evidence"] == []
    assert not result["conservative_alias_check"]["current_shared_cik_observed"]
    assert all(not row["verified_current_submission_association"] for row in result["rows"])


def test_punctuation_is_not_silently_repaired_to_create_a_ticker_match(tmp_path):
    snapshot(tmp_path, tickers=("BRK-B",))
    result = entity.runtime(tmp_path, ["BRK.B", "brk-b"])
    assert result["evidence_by_ticker"]["BRK.B"]["status"] == "UNMATCHED_IN_USABLE_LOCAL_SNAPSHOTS"
    assert result["evidence_by_ticker"]["BRK-B"]["verified_current_submission_association"]


def test_duplicate_occurrences_of_ticker_in_one_cik_are_not_multiple_issuer_ambiguity(tmp_path):
    snapshot(tmp_path, tickers=("AAA", "AAA"))
    row = entity.runtime(tmp_path, ["AAA"])["rows"][0]
    assert row["verified_current_submission_association"]
    assert len(row["matches"]) == 2 and len(row["matched_ciks"]) == 1


def test_unknown_dates_are_not_loaded_and_absent_directory_is_explicit(tmp_path):
    absent = entity.runtime(tmp_path, ["AAA"])
    assert not absent["submissions_directory_present"] and absent["selected_snapshot_count"] == 0
    snapshot(tmp_path, date="2026-08-01")
    result = entity.runtime(tmp_path, ["AAA"])
    assert result["submissions_directory_present"] and result["selected_snapshot_count"] == 0
    assert not result["rows"][0]["verified_current_submission_association"]


def test_query_order_deduplication_and_output_are_deterministic(tmp_path):
    snapshot(tmp_path, 2, name="B", tickers=("BBB",))
    snapshot(tmp_path, 1, name="A", tickers=("AAA",))
    first = entity.runtime(tmp_path, ["BBB", "AAA", "aaa"])
    second = entity.runtime(tmp_path, ["AAA", "BBB"])
    assert first == second and first["requested_ticker_count"] == 2
    assert first["downloaded_files"] == first["Provider_calls"] == first["tokenizer_calls"] == 0
    assert first["Student_calls"] == first["GPU_calls"] == 0
    assert not first["support_generation_allowed"] and not first["training_allowed"]


@pytest.mark.parametrize("tickers", ["AAA", [None], [" A "], ["../../secret"]])
def test_invalid_query_does_not_create_a_source_lookup(tickers, tmp_path):
    with pytest.raises(ValueError):
        entity.runtime(tmp_path, tickers)


def test_runtime_never_writes_to_the_local_metadata_archive(tmp_path):
    path = snapshot(tmp_path)
    before = {
        str(p.relative_to(tmp_path)): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()
    }
    entity.runtime(tmp_path, ["AAA"])
    after = {
        str(p.relative_to(tmp_path)): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()
    }
    assert before == after and str(path.relative_to(tmp_path)) in after
