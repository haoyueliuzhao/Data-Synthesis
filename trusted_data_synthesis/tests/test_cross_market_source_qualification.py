"""Synthetic manifests and mocked PDF parser; no model or network work."""

import json
import socket
from pathlib import Path

import prepare_cross_market_sources_20260926 as m
import pytest


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("unexpected network call")

    monkeypatch.setattr(socket, "create_connection", forbidden)


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.fixture
def small_lake(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "LAKE", tmp_path / "lake")
    monkeypatch.setattr(m, "RAW", tmp_path / "output")
    monkeypatch.setattr(m, "SECURITIES_PER_SOURCE", 1)
    for source, (directory, host, width) in m.SOURCES.items():
        objects = []
        for code in ("1".zfill(width), "2".zfill(width)):
            for year in range(2019, 2024):
                rel = (
                    f"{directory.split('/')[0]}/reports/stock_code={code}"
                    f"/year={year}/{code}_{year}.pdf"
                )
                path = m.LAKE / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                payload = f"not parsed before registration: {source}/{code}/{year}".encode()
                path.write_bytes(payload)
                objects.append(
                    dict(
                        source_id=source,
                        object_type="pdf",
                        validation_status="passed",
                        response_status=200,
                        content_sha256=m.sha(payload),
                        content_size_bytes=len(payload),
                        storage_uri="/archive/raw_financial_data_lake/data/fin_raw/" + rel,
                        raw_object_id=source + "_" + code + "_" + str(year),
                        source_publish_date=f"{year + 1}-03-01",
                        original_url=f"https://{host}/{code}/{year}.pdf",
                        request_params=dict(
                            stock_code=code,
                            company_name="Synthetic " + code,
                            year=str(year),
                            report_type="annual",
                            publish_date=f"{year + 1}-03-01",
                            announcement_id=str(year),
                            url=f"https://{host}/{code}/{year}.pdf",
                        ),
                    )
                )
        dump(m.LAKE / directory / "snapshot_date=2026-07-24/manifest.json", {"objects": objects})
    return tmp_path


def test_metadata_hash_order_is_fixed_and_not_source_value_selected(small_lake):
    first = m.metadata_inventory()
    assert len(first["roster"]) == 2
    assert sum(len(r["documents"]) for r in first["roster"]) == 10
    for path in m.LAKE.glob("*/**/manifest.json"):
        value = m.read(path)
        value["objects"].reverse()
        for row in value["objects"]:
            row["irrelevant_fake_financial_value"] = -999999
        dump(path, value)
    second = m.metadata_inventory()
    assert first["roster"] == second["roster"]
    assert first["no_PDF_or_financial_value_read"] is True
    assert all(r["issuer_cluster_status"].startswith("UNRESOLVED") for r in first["roster"])


def test_no_roster_expansion_when_metadata_pool_insufficient(small_lake, monkeypatch):
    monkeypatch.setattr(m, "SECURITIES_PER_SOURCE", 3)
    with pytest.raises(ValueError, match="at_least32_metadata_eligible"):
        m.metadata_inventory()


def test_missing_and_invalid_receipts_are_retained(small_lake):
    path = next(m.LAKE.glob("cninfo/**/manifest.json"))
    value = m.read(path)
    row = dict(value["objects"][0])
    row["original_url"] = "https://bad.example/file"
    row["request_params"] = {**row["request_params"], "url": row["original_url"]}
    value["objects"].append(row)
    dump(path, value)
    result = m.metadata_inventory()
    assert any("original_official_host" in r["reason"] for r in result["rejected"])


def test_receipt_conflict_cannot_choose_by_amount(small_lake):
    path = next(m.LAKE.glob("cninfo/**/manifest.json"))
    value = m.read(path)
    row = {**value["objects"][0], "content_sha256": "a" * 64}
    value["objects"].append(row)
    dump(path, value)
    result = m.metadata_inventory()
    assert any(r["reason"] == "same_vintage_conflicting_receipts" for r in result["rejected"])


def test_raw_path_escape_and_symlink_rejected(small_lake):
    with pytest.raises(ValueError, match="regular_confined_PDF"):
        m.local_path("/archive/raw_financial_data_lake/data/fin_raw/../outside.pdf")
    raw = next(m.LAKE.glob("cninfo/reports/**/*.pdf"))
    link = m.LAKE / "link.pdf"
    link.symlink_to(raw)
    with pytest.raises(ValueError, match="regular_confined_PDF"):
        m.local_path("/archive/raw_financial_data_lake/data/fin_raw/link.pdf")


@pytest.fixture
def work(small_lake, monkeypatch):
    from finraw import cn_financial_statements as parser

    doc = m.metadata_inventory()["roster"][0]["documents"][0]
    plan = dict(
        id="synthetic_plan:1",
        parser_attempts_per_document=2,
        total_parser_attempt_cap=2,
        maximum_statement_pages=20,
        maximum_unit_carry_pages=12,
        maximum_statement_carry_pages=4,
        maximum_result_bytes=1024 * 1024,
        document_count=1,
        metadata_inventory={"roster": [{"documents": [doc]}]},
        readiness_gates=["issuer_identity"],
    )
    calls = []

    def parse(path, **kwargs):
        assert kwargs["entity_id"].startswith("unresolved_security:")
        assert kwargs["source_id"] == doc["source_id"]
        assert (m.RAW / "budget.json").exists()
        calls.append(path)
        return parser.ParsedDocument(
            [], [], [dict(metric_hint="revenue", currency="CNY", evidence_status="verified")], {}
        )

    monkeypatch.setattr(parser, "parse_cninfo_pdf", parse)
    return plan, doc, calls, parser


def test_completed_document_reused_without_new_parse_or_budget(work):
    plan, doc, calls, _ = work
    first = m.document_job(plan, doc)
    assert m.document_job(plan, doc) == first
    assert len(calls) == 1
    assert m.read(m.RAW / "budget.json")["parser_attempts"] == 1
    summary = m.summarize(plan)
    assert summary["candidate_count"] == 1
    assert summary["panel_ready"] is summary["evaluation_started"] is False
    assert summary["independent_issuer_count"] is None


def test_changed_PDF_invalidates_saved_extraction(work):
    plan, doc, _, _ = work
    m.document_job(plan, doc)
    Path(doc["path"]).write_bytes(b"changed")
    with pytest.raises(ValueError, match="actual_PDF_bytes"):
        m.document_job(plan, doc)
    assert m.read(m.RAW / "budget.json")["parser_attempts"] == 1


def test_two_resource_errors_consume_finite_budget_and_are_saved(work, monkeypatch):
    plan, doc, _, parser = work

    def fail(*args, **kwargs):
        raise MemoryError("synthetic")

    monkeypatch.setattr(parser, "parse_cninfo_pdf", fail)
    assert m.document_job(plan, doc)["status"] == "RESOURCE_RETRY"
    assert m.document_job(plan, doc)["status"] == "RESOURCE_RETRY"
    with pytest.raises(ValueError, match="document_attempt_cap"):
        m.document_job(plan, doc)
    assert len(list((m.RAW / "resource_errors").rglob("*.json"))) == 2
    assert m.read(m.RAW / "budget.json")["parser_attempts"] == 2


def test_parser_error_preserved_and_not_retried(work, monkeypatch):
    plan, doc, _, parser = work

    def fail(*args, **kwargs):
        raise ValueError("synthetic malformed PDF")

    monkeypatch.setattr(parser, "parse_cninfo_pdf", fail)
    assert m.document_job(plan, doc)["status"] == "PARSE_FAILED"
    assert m.document_job(plan, doc)["status"] == "PARSE_FAILED"
    assert m.read(m.RAW / "budget.json")["parser_attempts"] == 1


def test_summary_requires_all_exact_documents(work):
    plan, doc, _, _ = work
    with pytest.raises(ValueError, match="complete_fixed_document_inventory"):
        m.summarize(plan)
    m.document_job(plan, doc)
    altered = {**plan, "metadata_inventory": {"roster": [{"documents": [{**doc, "year": 2010}]}]}}
    with pytest.raises(ValueError, match="exact_completed_document_identities"):
        m.summarize(altered)


def test_writes_are_confined_and_immutable(small_lake):
    with pytest.raises(ValueError, match="confined_output"):
        m.write(small_lake / "outside.json", {})
    m.write(m.RAW / "fixed.json", {"a": 1})
    m.write(m.RAW / "fixed.json", {"a": 1})
    with pytest.raises(ValueError, match="immutable_conflict"):
        m.write(m.RAW / "fixed.json", {"a": 2})


def test_emit_accepts_already_timestamped_results(capsys):
    m.emit({"at": "test-time", "event": "done"})
    assert json.loads(capsys.readouterr().out)["at"] == "test-time"
