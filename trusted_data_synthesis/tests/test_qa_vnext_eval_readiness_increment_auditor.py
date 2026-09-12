"""Independent new-source audit controls; synthetic original HTML/JSON only."""

import copy
import hashlib
import importlib.util
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

import pytest
from lxml import html

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/audit_qa_vnext_eval_readiness_increment.py"
SPEC = importlib.util.spec_from_file_location("test_UNP_source_auditor", SCRIPT)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def document(
    *,
    cover="December 31, 2024",
    unit="Millions",
    definition=audit.DEFINITION,
    cfi="(20)",
    dividend="(30)",
    auxiliary="",
):
    return (
        f"<html><p>FORM 10-K For the fiscal year ended {cover}</p><p>{definition}</p>"
        f"<table><tr><td>{unit}</td><td>2024</td><td>2023</td>{auxiliary}</tr>"
        "<tr><td>Cash provided by operating activities</td><td>$100</td><td>$80</td></tr>"
        f"<tr><td>Cash used in investing activities</td><td>{cfi}</td><td>(10)</td></tr>"
        f"<tr><td>Dividends paid</td><td>{dividend}</td><td>(20)</td></tr>"
        "<tr><td>Free cash flow</td><td>$50</td><td>$50</td></tr></table></html>"
    )


def table(value):
    dom = html.fromstring(value)
    grid = audit.base.original_grid(dom.xpath("//table")[0])
    headers, rows, labels, resolution = audit.unp_headers(grid, audit.base.normalized_text(dom))
    return grid, headers, rows, labels, resolution


def native_anchor():
    record = {
        "start": "2024-01-01",
        "end": "2024-12-31",
        "val": 100000000,
        "accn": "test-accession",
        "filed": "2025-02-07",
        "form": "10-K",
    }
    pointer = "/facts/us-gaap/NetCashProvidedByUsedInOperatingActivities/units/USD/0"
    original = {
        "cik": 100885,
        "facts": {
            "us-gaap": {"NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": [record]}}}
        },
    }
    observation = {
        "period_start": record["start"],
        "period_end": record["end"],
        "accession": record["accn"],
        "filing_date": record["filed"],
        "cfo_anchor": {
            "source_cluster": audit.CIK,
            "metric_id": "net_cash_provided_by_used_in_operating_activities",
            "pointer": pointer,
            "record": copy.deepcopy(record),
            "all_equal_source_occurrences": [{"pointer": pointer, "record": copy.deepcopy(record)}],
        },
    }
    return observation, original


def test_complete_original_physical_cells_signed_amounts_and_anchor():
    grid, headers, selected, _, resolution = table(document())
    assert [row["period_end"] for row in headers] == ["2024-12-31", "2023-12-31"]
    values = [
        audit.base.logical_amount(grid[index], headers[0], headers, grid[headers[0]["row"]])[0]
        for index in selected
    ]
    assert values == [Decimal(100), Decimal(-20), Decimal(-30), Decimal(50)]
    assert resolution["native_same_accession_annual_CFO_confirmation_required"]
    observation, original = native_anchor()
    audit.verify_anchor(observation, values, original)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"cover": "September 30, 2024"},
        {"cover": "December 31, 2023"},
        {"unit": "Thousands"},
        {"unit": "Millions of euros"},
        {"definition": audit.DEFINITION.replace("and dividends paid", "")},
        {"definition": audit.DEFINITION.replace("less", "plus")},
        {"auxiliary": "<td>Change %</td>"},
        {"auxiliary": "<td>2024</td>"},
    ],
)
def test_header_definition_and_scale_changes_cannot_pass_by_numeric_closure(kwargs):
    with pytest.raises(ValueError):
        table(document(**kwargs))


def test_unique_cover_after_long_hidden_metadata_prefix_is_not_truncated():
    prefix = "<p>FORM 10-K</p><div style='display:none'>" + "hidden metadata " * 10000 + "</div>"
    value = document().replace("<html>", "<html>" + prefix)
    _, headers, _, _, resolution = table(value)
    assert resolution["cover_text_start"] > 125575
    assert [row["period_end"] for row in headers] == ["2024-12-31", "2023-12-31"]
    assert resolution["native_same_accession_annual_CFO_confirmation_required"]


@pytest.mark.parametrize("extra_year", [2024, 2023])
def test_multiple_full_document_cover_literals_rejected_even_if_same_year(extra_year):
    value = document().replace(
        "</html>", f"<p>For fiscal year ended December 31, {extra_year}</p></html>"
    )
    with pytest.raises(ValueError, match="unambiguous"):
        table(value)


def test_no_FORM_10K_marker_in_first_3000_characters_rejected():
    with pytest.raises(ValueError, match="FORM 10-K"):
        table(document().replace("FORM 10-K", "ANNUAL REPORT"))
    value = document().replace("<html>", "<html><div>" + "hidden metadata " * 1000 + "</div>")
    with pytest.raises(ValueError, match="FORM 10-K"):
        table(value)


@pytest.mark.parametrize(
    "mutation",
    [
        "cik",
        "pointer",
        "currency",
        "date",
        "filing",
        "accession",
        "value",
        "CFI_sign",
        "dividend_sign",
        "closure",
    ],
)
def test_independent_native_anchor_and_signed_formula_reject_mutation(mutation):
    observation, original = native_anchor()
    values = [Decimal(100), Decimal(-20), Decimal(-30), Decimal(50)]
    if mutation == "cik":
        original["cik"] = 100884
    elif mutation == "pointer":
        observation["cfo_anchor"]["record"]["val"] = 101000000
    elif mutation == "currency":
        observation["cfo_anchor"]["pointer"] = observation["cfo_anchor"]["pointer"].replace(
            "USD", "EUR"
        )
    elif mutation == "date":
        observation["period_start"] = "2023-12-31"
    elif mutation == "filing":
        observation["filing_date"] = "2025-02-08"
    elif mutation == "accession":
        observation["accession"] = "other-filing"
    elif mutation == "value":
        values[0] = Decimal(100000)
        values[3] = sum(values[:3])
    elif mutation == "CFI_sign":
        values[1], values[3] = Decimal(20), Decimal(90)
    elif mutation == "dividend_sign":
        values[2], values[3] = Decimal(30), Decimal(110)
    else:
        values[3] = Decimal(49)
    with pytest.raises((ValueError, KeyError)):
        audit.verify_anchor(observation, values, original)


@pytest.mark.parametrize(
    "question,unit",
    [
        (
            "What is the change from the period 2023-01-01 through 2023-12-31 "
            "to the period 2024-01-01 through 2024-12-31 in USD millions?",
            "million USD",
        ),
        (
            "What is the year-over-year growth in the period "
            "2024-01-01 through 2024-12-31 in percent?",
            "percent",
        ),
        (
            "What is the YoY percentage change for the period 2024-01-01 through 2024-12-31?",
            "percent",
        ),
    ],
)
def test_public_intervals_come_from_saved_question_not_private_target(question, unit):
    available = {
        "2023-12-31": ("2023-01-01", Decimal(50), "same-def"),
        "2024-12-31": ("2024-01-01", Decimal(80), "same-def"),
    }
    assert audit.public_intervals(question, available, unit) == ("2023-12-31", "2024-12-31")


@pytest.mark.parametrize(
    "question,unit",
    [
        ("What is the change in the period 2024-01-01 through 2024-12-31?", "million USD"),
        ("What is the growth in the period 2024-01-01 through 2024-12-31?", "percent"),
        ("What is the YoY growth in the period 2024-02-01 through 2024-12-31?", "percent"),
        ("What is the YoY growth in 2024?", "percent"),
        (
            "What is previous minus current from the period 2023-01-01 through 2023-12-31 "
            "to the period 2024-01-01 through 2024-12-31?",
            "million USD",
        ),
    ],
)
def test_public_ambiguous_or_wrong_interval_and_direction_rejected(question, unit):
    available = {
        "2023-12-31": ("2023-01-01", Decimal(50), "same-def"),
        "2024-12-31": ("2024-01-01", Decimal(80), "same-def"),
    }
    with pytest.raises(ValueError):
        audit.public_intervals(question, available, unit)


def test_public_amount_and_growth_are_recomputed_from_independent_table_totals():
    obj = object.__new__(audit.UNPAudit)
    obj.source_periods = {
        ("table", "2023-12-31"): ("2023-01-01", Decimal(50), "definition"),
        ("table", "2024-12-31"): ("2024-01-01", Decimal(80), "definition"),
    }
    public = {
        "sources": [{"source_kind": "original_issuer_reconciliation", "source_id": "table"}],
        "question": (
            "What is the year-over-year growth in company-defined free cash flow "
            "in the period 2024-01-01 through 2024-12-31 in percent?"
        ),
        "quantity_contract": {
            "unit": "percent",
            "decimal_places": 2,
            "rounding": "half away from zero",
        },
    }
    assert obj.public_target(public) == Decimal(60)
    obj.source_periods["table", "2023-12-31"] = ("2023-01-01", Decimal(0), "definition")
    with pytest.raises(ValueError, match="positive"):
        obj.public_target(public)


def test_different_definition_cannot_be_hidden_by_equal_endpoint_values():
    obj = object.__new__(audit.UNPAudit)
    obj.source_periods = {
        ("table", "2023-12-31"): ("2023-01-01", Decimal(50), "old-definition"),
        ("table", "2024-12-31"): ("2024-01-01", Decimal(50), "new-definition"),
    }
    public = {
        "sources": [{"source_kind": "original_issuer_reconciliation", "source_id": "table"}],
        "question": (
            "What is the year-over-year growth in company-defined free cash flow "
            "in the period 2024-01-01 through 2024-12-31 in percent?"
        ),
        "quantity_contract": {
            "unit": "percent",
            "decimal_places": 2,
            "rounding": "half away from zero",
        },
    }
    with pytest.raises(ValueError, match="same full issuer definition"):
        obj.public_target(public)


def test_pinned_byte_reader_rejects_changed_bytes_and_symlink(tmp_path):
    path = tmp_path / "source"
    path.write_bytes(b"source")
    pin = {"path": "source", "bytes": 6, "sha256": hashlib.sha256(b"source").hexdigest()}
    assert audit.pinned_bytes(tmp_path, pin) == b"source"
    path.write_bytes(b"mutate")
    with pytest.raises(ValueError):
        audit.pinned_bytes(tmp_path, pin)
    (tmp_path / "link").symlink_to(path)
    with pytest.raises(ValueError):
        audit.pinned_bytes(tmp_path, {**pin, "path": "link"})


def test_auditor_imports_no_task_generator_or_issuer_adapter():
    import ast

    tree = ast.parse(SCRIPT.read_text())
    imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert not any(
        value
        and any(
            name in value
            for name in ("issuer_tables", "native_facts", "factory", "pipeline", "plans")
        )
        for value in imports
    )
    assert (
        "--directory" in SCRIPT.read_text() and "zero_new_tasks_is_supported" in SCRIPT.read_text()
    )
    assert json.loads(json.dumps(audit.RAW_IDS)) == audit.RAW_IDS


def registered(kind, **fields):
    value = {"schema_version": "finance_qa_vnext_task_build.v1." + kind, **fields}
    return {**value, "id": kind + ":" + hashlib.sha256(audit.canonical(value)).hexdigest()}


def test_synthetic_complete_source_path_matches_original_definition_identity(tmp_path, monkeypatch):
    raw_html = document().encode()
    dom = html.fromstring(raw_html)
    node = dom.xpath("//table")[0]
    grid, headers, selected, labels, resolution = table(raw_html)
    text, table_text = audit.base.normalized_text(dom), audit.base.normalized_text(node)
    shape = {
        "source_cluster": audit.CIK,
        "target": "issuer_defined_free_cash_flow",
        "definition_quote": audit.DEFINITION,
        "component_labels": [labels[i] for i in selected[:-1]],
        "signed_adjustments_as_printed": True,
    }
    definition = (
        "issuer_definition_"
        + hashlib.sha256(
            json.dumps(shape, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()[:24]
    )
    structure = {
        "rows": grid,
        "headers": headers,
        "selected_rows": selected,
        "labels": labels,
        "original_labels": labels,
        "header_period_resolution": resolution,
        "definition_quote": audit.DEFINITION,
        "definition_text_start": text.index(audit.DEFINITION),
        "definition_text_end": text.index(audit.DEFINITION) + len(audit.DEFINITION),
        "table_text": table_text,
        "table_text_start": text.index(table_text),
        "table_text_end": text.index(table_text) + len(table_text),
        "nearby_source_text": text,
    }
    table_record = registered(
        "issuer_source_table",
        table_id="table",
        raw_object_id="raw-html",
        raw_sha256=hashlib.sha256(raw_html).hexdigest(),
        table_xpath=node.getroottree().getpath(node),
        table_index=0,
        accession="test-accession",
        source_cluster=audit.CIK,
        source_definition_identity=definition,
        definition_shape=shape,
        structure=structure,
    )
    observation, original = native_anchor()
    observation.update(table_id="table", source_cluster=audit.CIK, definition_shape=shape, rows=[])
    observation["cfo_anchor"]["raw_object_id"] = "raw-json"
    for row_index in selected:
        amount, reference = audit.base.logical_amount(grid[row_index], headers[0], headers, grid[0])
        observation["rows"].append(
            {"row_index": row_index, "value": str(amount), "cell_reference": reference}
        )
    issuer = {"tables": [table_record], "observations": [observation]}
    monkeypatch.setattr(
        audit,
        "read",
        lambda path: issuer if Path(path).name == "issuer_source_tables.json" else {"tasks": []},
    )
    obj = object.__new__(audit.UNPAudit)
    obj.stage = tmp_path
    obj.new_sources = {
        "raw-html": {
            "raw_object": {
                "raw_object_id": "raw-html",
                "content_sha256": table_record["raw_sha256"],
                "storage_uri": "/cik=0000100885/accession=test-accession/source.htm",
            }
        }
    }
    obj.raw = {"raw-json": {"raw_object_id": "raw-json"}}
    obj.dom, obj.native, obj.issuer, obj.grids, obj.header_sets, obj.selected_rows = (
        {},
        {},
        {},
        {},
        {},
        {},
    )
    obj.tables, obj.values, obj.counts = {"atomic_facts": []}, {}, Counter()
    obj.original_file = lambda raw: (
        raw_html if raw["raw_object_id"] == "raw-html" else json.dumps(original).encode()
    )
    obj.verify_sources()
    assert obj.counts["new_UNP_tables"] == obj.counts["new_UNP_periods"] == 1
    assert obj.source_periods["table", "2024-12-31"] == ("2024-01-01", Decimal(50), definition)


def test_zero_increment_task_path_is_valid_without_assuming_minimum(tmp_path, monkeypatch):
    payloads = {
        "catalog.json": registered("fixed_task_catalog", tasks=[]),
        "stage_freeze.json": registered("incremental_task_freeze", rule={"source_split": {}}),
        "pattern_compilations.json": [],
        "all_leaf_usage.json": {},
        "canonical_task_registry.json": registered("incremental_target_registry", tasks=[]),
        "rewrite_budget_ledger.json": {
            "policy": {"request_cap": 34, "token_cap": 330752, "per_task_cap": 2},
            "reservations": [],
            "conservative_charged_tokens": 0,
            "previous_registered_debit": 221538,
            "cumulative_policy": {"prior_debits": [{"tokens": 221538}]},
        },
    }
    monkeypatch.setattr(audit, "read", lambda path: payloads[Path(path).name])
    monkeypatch.setattr(audit.base, "read", lambda path: payloads[Path(path).name])
    obj = object.__new__(audit.UNPAudit)
    obj.stage, obj.counts, obj.old_ids = tmp_path, Counter(), {str(i) for i in range(243)}
    obj.index = lambda *args: {}
    assert obj.verify_tasks() == []
