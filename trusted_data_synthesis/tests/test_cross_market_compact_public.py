"""Synthetic lossless-encoding and unchanged-runtime source-contract checks."""

import copy

import cross_market_compact_public_20260927 as m
import pytest


def fixture():
    documents, sources = [], []
    for document_index in range(2):
        raw_id, digest = f"original-report-{document_index}", str(document_index) * 64
        url = f"https://original.example/report-{document_index}.pdf"
        documents.append(
            dict(
                raw_object_id=raw_id,
                raw_sha256=digest,
                original_url=url,
                source_id="official-report-provider",
                source_publish_date="2020-04-24",
                financial_qualification_record_id=f"qualification:{document_index}",
                complete_original_pdf=dict(path=f"/original/{document_index}.pdf", sha256=digest),
                complete_original_page_text=dict(path=f"/original/{document_index}.json"),
            )
        )
        for period_index in range(2):
            sources.append(
                dict(
                    source_id=f"pdf_source:{document_index}{period_index}" + "a" * 62,
                    source_kind="official_report_pdf_numeric_record",
                    raw_object_id=raw_id,
                    raw_sha256=digest,
                    original_url=url,
                    native_pointer=f"pdf://{digest}#page=75&row=27&period_slot={period_index + 1}",
                    concept="pdf-financial:revenue",
                    label="营业总收入",
                    definition=dict(
                        metric_id="revenue",
                        original_label="营业总收入",
                        normalized_label="营业总收入",
                        statement_type="income_statement",
                        accounting_basis="native_original_report_not_US_GAAP_relabelled",
                        scope="consolidated_entity",
                        currency="CNY",
                    ),
                    unit="CNY",
                    record=dict(
                        start=f"{2018 + period_index}-01-01",
                        end=f"{2018 + period_index}-12-31",
                        val="-1234000.50",
                    ),
                    evidence=dict(
                        page=75,
                        table=f"original-table:{document_index}",
                        row=27,
                        period_slot=period_index + 1,
                        parser_word_index=period_index + 9,
                        raw_value_text="(1,234,000.50)",
                        unit_header="合并利润表\n单位:元 币种:人民币\n2019 年度 2018 年度",
                        financial_fact_id=f"fact:{document_index}{period_index}",
                        full_original_evidence_sha256="b" * 64,
                    ),
                )
            )
    return dict(
        question="Calculate the signed change in revenue from 2018 to 2019.",
        sources=sources,
        source_documents=documents,
        period_contract=dict(task_id="task:original", quantity="difference"),
        quantity_contract=dict(
            unit="million CNY", decimal_places=2, rounding="half_away_from_zero"
        ),
        source_policy=dict(
            no_private_solution_role_filter=True, retained_scientific_rule="original"
        ),
        tool_contract=dict(
            numeric_read_arguments=["source_id", "unit"], no_cross_currency_arithmetic=True
        ),
    )


def test_roundtrip_preserves_all_rows_financial_strings_and_original_document_versions():
    original = fixture()
    untouched = copy.deepcopy(original)
    projected, audit = m.compact(original)
    assert original == untouched
    assert m.restore(projected, audit) == original
    assert len(projected["sources"]) == 4
    assert [row["source_id"] for row in projected["sources"]] == [
        "S0001",
        "S0002",
        "S0003",
        "S0004",
    ]
    assert set(projected) == set(original)
    for old, new in zip(original["sources"], projected["sources"], strict=True):
        assert {
            key: value
            for key, value in old.items()
            if key not in {"source_id", "definition", "evidence"}
        } == {
            key: value
            for key, value in new.items()
            if key not in {"source_id", "definition", "evidence"}
        }
        assert new["evidence"]["raw_value_text"] == old["evidence"]["raw_value_text"]
    for old, new in zip(original["source_documents"], projected["source_documents"], strict=True):
        assert new["source_publish_date"] == old["source_publish_date"]
        assert len(new["definitions"]) == len(new["statement_tables"]) == 1
        assert new["definitions"]["D001"] == original["sources"][0]["definition"]
    assert len(m._encode(projected)) < len(m._encode(original))


def test_audit_does_not_store_financial_definitions_values_or_unit_headers():
    projected, audit = m.compact(fixture())
    assert set(audit) == {
        "schema",
        "original_public_sha256",
        "projected_public_sha256",
        "documents",
        "sources",
    }
    for row in audit["sources"]:
        assert set(row) == {"source_id", "original_source_id", "removed_fields"}
        assert set(row["removed_fields"]) == {"evidence"}
        assert set(row["removed_fields"]["evidence"]) == m.EVIDENCE_AUDIT_FIELDS
    for row in audit["documents"]:
        assert set(row["removed_fields"]) == m.DOCUMENT_AUDIT_FIELDS
    assert projected["sources"][0]["definition"] == {"ref": "D001"}
    assert projected["sources"][0]["evidence"]["table_ref"] == "T001"


@pytest.mark.parametrize("field", ["amount", "raw_amount", "definition", "header", "source_row"])
def test_projected_financial_values_are_used_and_never_replaced_from_audit(field):
    projected, audit = m.compact(fixture())
    if field == "amount":
        projected["sources"][0]["record"]["val"] = "9999"
    elif field == "raw_amount":
        projected["sources"][0]["evidence"]["raw_value_text"] = "9999"
    elif field == "definition":
        projected["source_documents"][0]["definitions"]["D001"]["scope"] = "different"
    elif field == "header":
        projected["source_documents"][0]["statement_tables"]["T001"]["unit_header"] = "million USD"
    else:
        projected["sources"].pop()
    # Even re-signing the projection cannot mask a changed original financial value.
    audit["projected_public_sha256"] = m._sha(projected)
    with pytest.raises(ValueError, match="restored_original_digest|source_count|source_order"):
        m.restore(projected, audit)


def test_equal_visible_table_headers_do_not_merge_distinct_original_tables():
    original = fixture()
    original["sources"][1]["evidence"]["table"] = "different-original-table"
    projected, audit = m.compact(original)
    tables = projected["source_documents"][0]["statement_tables"]
    assert len(tables) == 2
    assert tables["T001"] == tables["T002"]
    assert (
        projected["sources"][0]["evidence"]["table_ref"]
        != projected["sources"][1]["evidence"]["table_ref"]
    )
    assert m.restore(projected, audit) == original


def test_unknown_fields_are_preserved_instead_of_treated_as_audit():
    original = fixture()
    original["source_documents"][0]["amendment_note"] = "original publication only"
    original["sources"][0]["evidence"]["new_semantic_field"] = "original meaning"
    projected, audit = m.compact(original)
    assert projected["source_documents"][0]["amendment_note"] == "original publication only"
    assert projected["sources"][0]["evidence"]["new_semantic_field"] == "original meaning"
    assert m.restore(projected, audit) == original


def test_existing_runtime_reads_preserved_native_identity_and_exact_record():
    import fixed_kernel_cross_market_runtime_20260926 as runtime

    original = fixture()
    projected, _audit = m.compact(original)
    old_sources = runtime.SourceViewSources(original)
    new_sources = runtime.SourceViewSources(projected)
    assert new_sources.public == projected
    for old, new in zip(original["sources"], projected["sources"], strict=True):
        before = old_sources.read_source(dict(source_id=old["source_id"], unit="million CNY"))
        after = new_sources.read_source(dict(source_id=new["source_id"], unit="million CNY"))
        for key in (
            "source_id",
            "native_pointer",
            "source_raw_sha256",
            "source_url",
            "concept",
            "source_unit",
            "record",
            "actual_period",
            "exact_value",
            "unit",
            "conversion",
        ):
            assert after[key] == before[key]
