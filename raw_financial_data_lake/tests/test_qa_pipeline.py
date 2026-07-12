from __future__ import annotations

import json
from pathlib import Path

import pytest

from finraw.db.client import MetadataDB
from finraw.qa.export import export_qa_jsonl
from finraw.qa.pipeline import _answer_text, _answers_match, _recompute, build_qa


DERIVED_TYPES = [
    "difference",
    "yoy_growth",
    "qoq_growth",
    "ratio",
    "share",
    "multi_year_argmax",
    "multi_year_argmin",
    "industry_ranking",
    "industry_argmax",
    "industry_argmin",
    "ranking",
    "argmax",
    "argmin",
    "rolling_max",
    "rolling_min",
    "macro_time_series_argmax",
    "macro_time_series_argmin",
    "time_series_argmax",
    "time_series_argmin",
    "multi_condition_screening",
    "long_window_return",
]


def _insert_node(db, kg_build: str, node_id: str, node_type: str) -> None:
    db.execute(
        "INSERT INTO kg_nodes (node_id, stable_node_id, kg_build_id, node_type, is_active) VALUES (?, ?, ?, ?, ?)",
        (node_id, node_id.split("@@")[0], kg_build, node_type, 1),
    )


def _insert_edge(
    db,
    kg_build: str,
    edge_id: str,
    source: str,
    target: str,
    relation: str,
) -> None:
    db.execute(
        "INSERT INTO kg_edges (edge_id, stable_edge_id, kg_build_id, src_node_id, dst_node_id, relation_type, is_active) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (edge_id, edge_id.split("@@")[0], kg_build, source, target, relation, 1),
    )


def _qa_fixture(tmp_path):
    db = MetadataDB(str(tmp_path / "qa.db"))
    db.init_schema()
    fact_build = "facts_1"
    kg_build = "kg_1"
    fact_id = "fact_1"
    db.execute(
        "INSERT INTO source_registry (source_id, source_name, source_type, authority_level) VALUES (?, ?, ?, ?)",
        ("sec_companyfacts", "SEC Company Facts", "api", "S1_official"),
    )
    db.execute(
        "INSERT INTO canonical_entities (entity_id, canonical_name, entity_type, build_id, is_active) VALUES (?, ?, ?, ?, ?)",
        ("AAPL_US", "Apple Inc.", "company", "entities_1", 1),
    )
    db.execute(
        "INSERT INTO metrics (metric_id, canonical_name, metric_category, period_type, build_id, is_active) VALUES (?, ?, ?, ?, ?, ?)",
        ("revenue", "revenue", "financial_statement", "period_flow", "metrics_1", 1),
    )
    db.execute(
        "INSERT INTO raw_objects (raw_object_id, source_id, object_type, storage_uri, original_url, content_sha256, validation_status) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            "raw_1",
            "sec_companyfacts",
            "json",
            "data/raw_1.json",
            "https://example.test/raw_1",
            "abc",
            "passed",
        ),
    )
    db.execute(
        "INSERT INTO source_metric_definitions (definition_id, source_id, metric_id, raw_concept_name, build_id, is_active) VALUES (?, ?, ?, ?, ?, ?)",
        (
            "definition_1",
            "sec_companyfacts",
            "revenue",
            "us-gaap:Revenue",
            "definitions_1",
            1,
        ),
    )
    db.execute(
        """
        INSERT INTO standardized_facts (
            fact_id, stable_fact_id, build_id, is_active, entity_id, metric_id,
            normalized_value, normalized_unit, normalized_currency, period_end,
            fiscal_year, fiscal_quarter, time_basis, metric_period_type,
            source_definition_id, source_id, raw_object_id, verification_status,
            graph_ready, graph_ready_reason, is_forecast
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            fact_id,
            fact_id,
            fact_build,
            1,
            "AAPL_US",
            "revenue",
            "383285",
            "million USD",
            "USD",
            "2023-09-30",
            2023,
            "FY",
            "fiscal_year",
            "period_flow",
            "definition_1",
            "sec_companyfacts",
            "raw_1",
            "single_source",
            1,
            "ready",
            0,
        ),
    )
    db.execute(
        """
        INSERT INTO kg_builds (
            kg_build_id, graph_schema_version, input_fact_build_id, input_qa_build_id,
            input_entity_build_id, input_metric_build_id, status, quality_status, is_active
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            kg_build,
            "3.0",
            fact_build,
            "derived_1",
            "entities_1",
            "metrics_1",
            "success",
            "passed",
            1,
        ),
    )
    nodes = {
        f"entity:AAPL_US@@{kg_build}": "Entity",
        f"fact:{fact_id}@@{kg_build}": "Fact",
        f"metric:revenue@@{kg_build}": "Metric",
        f"time:2023-FY@@{kg_build}": "TimePeriod",
        f"source:sec_companyfacts@@{kg_build}": "DataSource",
        f"raw_object:raw_1@@{kg_build}": "RawObject",
        f"source_definition:definition_1@@{kg_build}": "SourceDefinition",
    }
    for node_id, node_type in nodes.items():
        _insert_node(db, kg_build, node_id, node_type)
    fact_node = f"fact:{fact_id}@@{kg_build}"
    edge_specs = [
        ("edge_has_fact", f"entity:AAPL_US@@{kg_build}", fact_node, "HAS_FACT"),
        ("edge_measures", fact_node, f"metric:revenue@@{kg_build}", "MEASURES"),
        ("edge_period", fact_node, f"time:2023-FY@@{kg_build}", "IN_PERIOD"),
        (
            "edge_source",
            fact_node,
            f"source:sec_companyfacts@@{kg_build}",
            "FROM_SOURCE",
        ),
        ("edge_raw", fact_node, f"raw_object:raw_1@@{kg_build}", "TRACED_TO"),
        (
            "edge_definition",
            fact_node,
            f"source_definition:definition_1@@{kg_build}",
            "USES_SOURCE_DEFINITION",
        ),
    ]
    for stable_id, source, target, relation in edge_specs:
        _insert_edge(db, kg_build, f"{stable_id}@@{kg_build}", source, target, relation)
    config = {
        "qa": {
            "quotas": {
                "single_fact_financial": 1,
                "single_fact_worldbank": 0,
                "single_fact_imf": 0,
                "single_fact_fred": 0,
            },
            "derived_quotas": {key: 0 for key in DERIVED_TYPES},
            "temporal_split": {"cutoff_year": 3000},
            "quality_gate": {
                "minimum_overall_pass_rate": 1.0,
                "critical_tasks": {"single_fact": 1},
                "max_critical_check_failures": 0,
            },
        }
    }
    return db, kg_build, config


def test_build_validate_split_and_export_qa(tmp_path):
    db, kg_build, config = _qa_fixture(tmp_path)
    report = build_qa(
        db,
        config,
        kg_build_id=kg_build,
        output_dir=str(tmp_path / "audit"),
        batch_size=10,
    )
    assert report["quality"]["passed_count"] == 1
    assert report["split"]["passed_sample_count"] == 1
    assert report["split"]["build_gate_status"] == "passed"
    qa_build_id = report["qa_build_id"]
    sample = dict(
        db.fetchone("SELECT * FROM qa_samples WHERE qa_build_id = ?", (qa_build_id,))
    )
    assert sample["validation_status"] == "passed"
    assert sample["template_id"]
    assert sample["template_hash"]
    assert "Apple Inc." in sample["question"]
    assert float(json.loads(sample["answer_value"])["value"]) == 383285
    exported = export_qa_jsonl(db, qa_build_id, str(tmp_path / "exports"))
    assert exported["sample_count"] == 1
    assert exported["sft_allowed_splits"] == ["train"]
    for family, files in exported["files"].items():
        for info in files.values():
            assert Path(info["path"]).exists(), family
            assert len(info["sha256"]) == 64
    assert exported["files"]["sft"]["train"]["rows"] == exported["split_counts"].get(
        "train", 0
    )
    db.close()


def test_export_rejects_build_without_passed_gate(tmp_path):
    db, kg_build, config = _qa_fixture(tmp_path)
    report = build_qa(
        db,
        config,
        kg_build_id=kg_build,
        output_dir=str(tmp_path / "audit"),
        batch_size=10,
    )
    qa_build_id = report["qa_build_id"]
    db.execute(
        "UPDATE qa_builds SET status = 'quality_failed', is_active = 0 WHERE qa_build_id = ?",
        (qa_build_id,),
    )
    with pytest.raises(RuntimeError, match="not exportable"):
        export_qa_jsonl(db, qa_build_id, str(tmp_path / "exports"))
    db.close()


def test_answers_match_checks_units_currency_rank_and_table_values():
    expected = {
        "value": "10",
        "unit": "million USD",
        "currency": "USD",
    }
    assert _answers_match(expected, dict(expected), None)
    assert not _answers_match(expected, {**expected, "unit": "USD"}, None)
    assert not _answers_match(expected, {**expected, "currency": "CNY"}, None)
    ranked = {
        "table": [
            {"rank": 1, "entity_id": "A", "value": 10},
            {"rank": 2, "entity_id": "B", "value": 9},
        ],
        "unit": "percent",
    }
    assert _answers_match(ranked, ranked, None)
    assert not _answers_match(
        ranked,
        {
            "table": [
                {"rank": 1, "entity_id": "A", "value": 10},
                {"rank": 2, "entity_id": "B", "value": 8},
            ],
            "unit": "percent",
        },
        None,
    )


def test_ranked_answer_text_contains_rank_entity_and_value():
    text = _answer_text(
        {"task_subtype": "ranking"},
        {
            "table": [
                {"rank": 1, "entity_id": "A", "value": 10},
                {"rank": 2, "entity_id": "B", "value": 9},
            ],
            "unit": "percent",
        },
        {"A": "Alpha", "B": "Beta"},
    )
    assert text == "1. Alpha: 10 percent; 2. Beta: 9 percent"


def test_ranking_recompute_uses_full_scope_but_returns_top_k():
    facts = [
        {
            "entity_id": entity,
            "normalized_value": value,
            "normalized_unit": "million USD",
        }
        for entity, value in [("A", "10"), ("B", "30"), ("C", "20")]
    ]
    observed, _ = _recompute("ranking", facts, {"top_k": 2})
    assert observed["table"] == [
        {"rank": 1, "entity_id": "B", "value": 30},
        {"rank": 2, "entity_id": "C", "value": 20},
    ]
