"""Synthetic issuer-specific definition/table and actual QA integration controls."""

import copy
import hashlib
import importlib.util
import json
from decimal import Decimal
from pathlib import Path

import pytest
from finraw.builds import ensure_build_schema, finish_build, start_build
from finraw.db.client import MetadataDB
from finraw.derived_facts import refresh_derived_facts
from finraw.fact_quality import enforce_fact_quality_gates
from finraw.fact_standardization import refresh_fact_standardization
from finraw.kg_builder import build_kg, ensure_kg_schema
from finraw.qa import pipeline
from lxml import html

from trusted_synthesis.experiments.finance_qa_vnext_task_build import factory, issuer_tables
from trusted_synthesis.experiments.finance_qa_vnext_task_build.archive import insert
from trusted_synthesis.experiments.finance_qa_vnext_task_build.native_facts import (
    populate_facts,
    populate_ontology,
)
from trusted_synthesis.experiments.finance_qa_vnext_task_build.protocol import METRIC_TAGS

SOURCE = """<html><body><p>We define free cash flow as net cash provided by operating activities
less capital expenditures plus legal settlements.</p><p>All amounts in millions of U.S. dollars.</p>
<table>
<tr><td>Years Ended</td><td>December 31, 2020</td><td>December 31, 2019</td></tr>
<tr><td>Net cash provided by operating activities</td><td>130</td><td>100</td></tr>
<tr><td>Capital expenditures</td><td>(90)</td><td>(70)</td></tr>
<tr><td>Legal settlements</td><td>2</td><td>1</td></tr>
<tr><td>Free cash flow</td><td>42</td><td>31</td></tr>
</table></body></html>"""


def structures(source=SOURCE):
    root = html.fromstring(source)
    return issuer_tables.table_structure(root.xpath("//table")[0], issuer_tables.text(root))


@pytest.mark.parametrize("layout", ["full_dates", "shared_month_day", "annotated_total"])
def test_independent_source_auditor_reads_issuer_header_variants(layout):
    source = SOURCE
    if layout == "shared_month_day":
        source = source.replace(
            "<td>Years Ended</td><td>December 31, 2020</td><td>December 31, 2019</td>",
            "<td>Years Ended December 31,</td><td>2020</td><td>2019</td>",
        )
    elif layout == "annotated_total":
        source = source.replace(">Free cash flow<", ">Free cash flow (1)<").replace(
            "</table>", "</table><p>(1) This is an explicit source footnote.</p>"
        )
    path = Path(__file__).resolve().parents[1] / "scripts/audit_qa_vnext_task_build.py"
    spec = importlib.util.spec_from_file_location("synthetic_source_auditor", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    auditor = module.Audit.__new__(module.Audit)
    auditor.grids = {"table": structures(source)["rows"]}
    public = {
        "question": (
            "What is the change in Example's company-defined free cash flow from "
            "2019-12-31 to 2020-12-31? Report in USD millions."
        ),
        "sources": [{"source_id": "table"}],
        "quantity_contract": {
            "unit": "million USD",
            "decimal_places": 2,
            "rounding": "half away from zero",
        },
    }
    assert auditor.public_target(public) == Decimal("11")


def test_colon_ends_explicit_definition_before_table_or_following_prose():
    source = SOURCE.replace(
        "We define free cash flow as net cash provided by operating activities\n"
        "less capital expenditures plus legal settlements.",
        "We calculate free cash flow as follows:",
    )
    assert structures(source)["definition_quote"] == "We calculate free cash flow as follows:"


def test_exact_subtracting_capex_clause_requires_complete_two_component_domain():
    quote = (
        "Free cash flow was calculated by subtracting capital expenditures from "
        "the most directly comparable GAAP measure, cash flows from operating activities "
        "(also referred to as cash flow from operations)."
    )
    issuer_tables.validate_definition_shape(
        quote, ["Cash flows from operating activities", "Capital expenditures"]
    )
    with pytest.raises(ValueError, match="subtraction_clause_complete_roles"):
        issuer_tables.validate_definition_shape(
            quote,
            ["Cash flows from operating activities", "Capital expenditures", "Legal settlements"],
        )


@pytest.mark.parametrize("marker", ["*", "(1)"])
def test_annotation_requires_real_following_note_not_its_own_label(marker):
    source = SOURCE.replace(">Free cash flow<", ">Free cash flow " + marker + "<")
    with pytest.raises(ValueError, match="footnote_requires_following_source_text"):
        structures(source)
    source = source.replace(
        "</table>", "</table><p>" + marker + " This is an explicit source note.</p>"
    )
    result = structures(source)
    annotation = result["label_annotations"][0]
    assert annotation["note_quote"] == marker + " This is an explicit source note."
    assert annotation["note_text_start"] >= result["table_text_end"]
    assert result["labels"][-1] == "Free cash flow"


def inputs(tmp_path, source=SOURCE):
    relative = "sec/filings/cik=0000002488/accession=fixture-filing/report.htm"
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    path.write_text(source, encoding="utf-8")
    encoded = path.read_bytes()
    entity = {
        "entity_id": "AMD_US",
        "canonical_name": "Synthetic Issuer",
        "entity_type": "company",
        "cik": "0000002488",
        "market": "US",
        "country": "US",
        "is_active": 1,
    }
    raw = {
        "raw_object_id": "fixture_html",
        "source_id": "sec_filings",
        "storage_uri": "/workspace/Data Synthesis/" + relative,
        "original_url": "https://example.invalid/synthetic-issuer",
        "content_sha256": hashlib.sha256(encoded).hexdigest(),
        "content_size_bytes": len(encoded),
        "validation_status": "passed",
    }
    document = {
        "document_id": "synthetic_original_document",
        "entity_id": "AMD_US",
        "period_end": "2020-12-31",
        "filing_date": "2021-02-15",
        "source_id": "sec_filings",
        "document_status": "passed",
        "is_active": 1,
        "raw_object_id": raw["raw_object_id"],
        "original_url": raw["original_url"],
        "storage_uri": raw["storage_uri"],
    }
    native_raw = {
        "raw_object_id": "fixture_native",
        "source_id": "sec_companyfacts",
        "content_sha256": "synthetic_native_SHA",
        "original_url": "https://example.invalid/synthetic-companyfacts",
        "storage_uri": "fixture://native",
        "validation_status": "passed",
    }
    observations = []
    for year, amount in ((2019, 100), (2020, 130)):
        row = {
            "val": amount * 1000000,
            "start": f"{year}-01-01",
            "end": f"{year}-12-31",
            "fy": year,
            "fp": "FY",
            "form": "10-K",
            "accn": "fixture-filing",
            "filed": "2021-02-15",
        }
        pointer = f"/CFO/{year}"
        observations.append(
            {
                "entity_id": "AMD_US",
                "source_cluster": "cik:0000002488",
                "metric_id": issuer_tables.CFO,
                "tag": METRIC_TAGS[issuer_tables.CFO][0],
                "record": row,
                "pointer": pointer,
                "raw_sha256": native_raw["content_sha256"],
                "raw_object_id": native_raw["raw_object_id"],
                "native_definition": {
                    "label": "Net operating cash flow",
                    "description": "Net cash provided by operating activities.",
                },
                "all_equal_source_occurrences": [{"pointer": pointer, "record": row}],
                "split": "train",
                "allowed_uses": ["train"],
            }
        )
    source_info = {"document": document, "raw_object": raw, "entity": entity}
    result = issuer_tables.parse_document(tmp_path, source_info, observations)
    issuer = {
        "sources": [source_info],
        "tables": result["tables"],
        "observations": result["observations"],
        "failures": result["failures"],
    }
    native = [
        {
            "entity": entity,
            "raw_object": native_raw,
            "observations": observations,
            "definitions": {observations[0]["tag"]: observations[0]["native_definition"]},
        }
    ]
    return issuer, native


def test_generic_complete_table_binds_definition_and_all_adjustments():
    result = structures()
    assert len(result["selected_rows"]) == 4
    assert result["definition_quote"].endswith("plus legal settlements.")
    assert issuer_tables.row_amount(result["rows"][2], result["headers"][0])[0] == Decimal("-90")


@pytest.mark.parametrize(
    "change,reason",
    [
        ("wrong_definition", "definition_and_complete_row_roles_disagree"),
        ("unknown_definition", "uninterpreted_definition_vocabulary"),
        ("missing_definition", "explicit_company_FCF_definition"),
        ("drop_adjustment", "definition_and_complete_row_roles_disagree"),
        ("no_annual_header", "explicit_annual_table_scope"),
        ("no_million_scale", "explicit_million_scale"),
    ],
)
def test_financial_relation_is_not_certified_by_a_closing_table_alone(change, reason):
    source = SOURCE
    if change == "wrong_definition":
        source = source.replace("plus legal settlements.", "plus dividends.")
    elif change == "unknown_definition":
        source = source.replace("plus legal settlements.", "plus stock-based compensation.")
    elif change == "missing_definition":
        source = source.replace(
            "We define free cash flow", "Investors sometimes discuss this number"
        )
    elif change == "drop_adjustment":
        source = source.replace("<tr><td>Legal settlements</td><td>2</td><td>1</td></tr>", "")
    elif change == "no_annual_header":
        source = source.replace("Years Ended", "Selected observations")
    elif change == "no_million_scale":
        source = source.replace("All amounts in millions of U.S. dollars.", "Selected figures.")
    with pytest.raises(ValueError, match=reason):
        structures(source)


@pytest.mark.parametrize("printed", ["—", "–", "-", "", "N/A"])
def test_dashes_or_missing_amounts_are_not_implicitly_zero(printed):
    assert issuer_tables.scalar(printed) is None
    assert issuer_tables.scalar("0") == 0


def test_same_filing_native_anchor_and_original_cell_values_are_required(tmp_path):
    issuer, native = inputs(tmp_path)
    assert len(issuer["observations"]) == 2 and not issuer["failures"]
    altered = copy.deepcopy(native[0]["observations"])
    altered[0]["record"]["val"] += 1
    source = issuer["sources"][0]
    result = issuer_tables.parse_document(tmp_path, source, altered)
    assert len(result["observations"]) == 1
    assert result["failures"][0]["reason"] == "issuer.same_filing_native_USD_CFO_anchor"


@pytest.mark.parametrize("realization", ["template", "accepted", "fallback"])
def test_issuer_native_facts_reach_actual_QA_build_export_without_a_universal_FCF_formula(
    tmp_path, realization
):
    issuer, native = inputs(tmp_path)
    db = MetadataDB(str(tmp_path / "issuer_integration.sqlite3"))
    db.init_schema()
    ensure_build_schema(db)
    ensure_kg_schema(db)
    entity_build = start_build(
        db, layer="entity", command="synthetic-issuer-control", prefix="fixture_entity"
    )
    entity = {**native[0]["entity"], "build_id": entity_build}
    insert(db, "canonical_entities", [entity])
    for source in ("sec_companyfacts", "sec_filings"):
        insert(
            db,
            "source_registry",
            [
                {
                    "source_id": source,
                    "source_name": "Synthetic fixture",
                    "source_type": "fixture",
                    "authority_level": "fixture",
                    "is_active": 1,
                }
            ],
        )
    insert(db, "raw_objects", [native[0]["raw_object"]])
    finish_build(db, entity_build, "success", "Synthetic control only")

    class FixtureArchive:
        def fetchall(self, query):
            if query == "SELECT * FROM metrics":
                return [
                    {
                        "metric_id": issuer_tables.CFO,
                        "canonical_name": "operating cash flow",
                        "metric_category": "financial_statement",
                        "period_type": "period_flow",
                        "default_unit": "monetary",
                    }
                ]
            assert query == "SELECT * FROM source_metric_definitions"
            return []

    populate_ontology(db, FixtureArchive(), native, issuer)
    _, _, bindings = populate_facts(db, native, issuer)
    refresh_fact_standardization(db, {})
    assert enforce_fact_quality_gates(db, {})["fact_quality_gate_status"] == "passed"
    refresh_derived_facts(
        db,
        {"kg": {"derived_policy": {"annual_filing_sources": ["sec_companyfacts", "sec_filings"]}}},
    )
    built = build_kg(db, {}, activate=False)
    kg = db.fetchone("SELECT * FROM kg_builds WHERE kg_build_id=?", (built["kg_build_id"],))
    assert kg["quality_status"] == "passed"
    facts = pipeline._load_facts_by_id(
        db, list(bindings), kg["input_fact_build_id"], kg["input_entity_build_id"]
    )
    usage = {key: {"split": "train", "allowed_uses": ["train"]} for key in bindings}
    selected, rejected, _ = factory.enumerate_bindings(facts, bindings, usage)
    assert not rejected
    assert len(selected["company_defined_metric"]) == 2
    items = selected["company_defined_metric"]
    kwargs = {}
    ledger = None
    if realization != "template":
        from trusted_synthesis.experiments.finance_qa_vnext_surface_build.budget import Ledger
        from trusted_synthesis.experiments.finance_qa_vnext_surface_build.protocol import qa_config
        from trusted_synthesis.experiments.finance_qa_vnext_surface_build.transport import (
            MODEL,
            Provider,
        )

        ledger = Ledger(tmp_path / "rewrite_budget.sqlite", "synthetic_stage")

        def sender(body, key):
            requested = json.loads(body["messages"][1]["content"])
            template = (
                requested["protected_question"]
                .replace("What is", "Calculate")
                .replace("What was", "Calculate")
            )
            if realization == "fallback":
                template = "Invented invalid question."
            content = {
                "rewrites": [
                    {"rewrite_version": "question_rewrite.v3.3", "question_template": template}
                ]
            }
            return json.dumps(
                {
                    "model": MODEL,
                    "usage": {"prompt_tokens": 50, "completion_tokens": 50},
                    "choices": [{"message": {"content": json.dumps(content)}}],
                }
            ).encode()

        kwargs = {
            "config": qa_config(),
            "provider_factory": lambda task: Provider(
                task, ledger, tmp_path, "TEST_KEY", sender=sender
            ),
        }
    build_id, candidates, plans, compilations, validation = factory.compile_batch(
        db, kg, items, facts, bindings, tmp_path, "issuer_QA", **kwargs
    )
    assert validation["passed_count"] == 2, validation
    if ledger:
        from trusted_synthesis.experiments.finance_qa_vnext_surface_build.stage import make_surface

        count = 2 if realization == "accepted" else 4
        assert ledger.snapshot()["sent_request_count"] == count
        for sample in db.fetchall("SELECT * FROM qa_samples"):
            candidate = next(
                row for row in candidates if row["candidate_id"] == sample["candidate_id"]
            )
            item = next(
                row
                for row in items
                if row["previous_fact_id"]
                == candidate["canonical_semantics"]["input_bindings"]["previous"]
                and (
                    "yoy_growth" if row["target"]["quantity"] == "relative_change" else "difference"
                )
                == candidate["task_subtype"]
            )
            public = factory.public_projection(
                sample["question"],
                [],
                {
                    "unit": item["target"]["unit"],
                    "currency": item["target"]["currency"],
                    "decimal_places": 2,
                    "rounding": "half away from zero",
                },
            )
            surface = make_surface(item, dict(sample), public, candidate, "synthetic_stage")
            if realization == "fallback":
                assert surface["category"] == "canonical_fallback"
                assert sample["question"] == sample["canonical_question"]
    exported, rejected = factory.export_batch(
        db, kg, build_id, items, candidates, plans, compilations, facts, bindings, usage, tmp_path
    )
    assert len(exported) == 2 and not rejected
    for reference in exported:
        bundle = json.loads((tmp_path / reference["path"]).read_bytes())
        assert len(bundle["public"]["sources"]) == 1
        assert "Legal settlements" in json.dumps(bundle["public"]["sources"])
        assert "answer_payload" not in json.dumps(factory.teacher_messages(bundle))
        if bundle["private"]["canonical_target"]["quantity"] == "difference":
            assert Decimal(bundle["private"]["answer_exact"]) == 11
            assert Decimal(bundle["private"]["basis_witnesses"][1]["output"]["value"]) == 11
    db.close()
