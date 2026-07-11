from __future__ import annotations

import json

from finraw.db.client import MetadataDB
from finraw.qa.export import export_qa_jsonl
from finraw.qa.pipeline import build_qa, _fact_path


def test_build_validate_split_and_export_qa(tmp_path):
    db = MetadataDB(str(tmp_path / "qa.db"))
    db.init_schema()
    fact_build = "facts_1"
    kg_build = "kg_1"
    fact_id = "fact_1"
    db.execute(
        "INSERT INTO canonical_entities (entity_id, canonical_name, entity_type, build_id, is_active) VALUES (?, ?, ?, ?, ?)",
        ("AAPL_US", "Apple Inc.", "company", "entities_1", 1),
    )
    db.execute(
        "INSERT INTO metrics (metric_id, canonical_name, metric_category, period_type, build_id, is_active) VALUES (?, ?, ?, ?, ?, ?)",
        ("revenue", "revenue", "financial_statement", "period_flow", "metrics_1", 1),
    )
    db.execute(
        """
        INSERT INTO standardized_facts (
            fact_id, stable_fact_id, build_id, is_active, entity_id, metric_id,
            normalized_value, normalized_unit, normalized_currency, fiscal_year,
            fiscal_quarter, time_basis, metric_period_type, source_id,
            verification_status, graph_ready, graph_ready_reason, is_forecast
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            2023,
            "FY",
            "fiscal_year",
            "period_flow",
            "sec_companyfacts",
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
    fact = {
        "fact_id": fact_id,
        "entity_id": "AAPL_US",
        "metric_id": "revenue",
        "source_id": "sec_companyfacts",
        "raw_object_id": None,
    }
    path = _fact_path(fact, kg_build)
    for node_id in path["node_ids"]:
        db.execute(
            "INSERT INTO kg_nodes (node_id, stable_node_id, kg_build_id, node_type, is_active) VALUES (?, ?, ?, ?, ?)",
            (node_id, node_id.split("@@")[0], kg_build, "Fact", 1),
        )
    for edge_id in path["edge_ids"]:
        db.execute(
            "INSERT INTO kg_edges (edge_id, stable_edge_id, kg_build_id, src_node_id, dst_node_id, relation_type, is_active) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                edge_id,
                edge_id.split("@@")[0],
                kg_build,
                path["node_ids"][0],
                path["node_ids"][1],
                "TEST",
                1,
            ),
        )
    config = {
        "qa": {
            "quotas": {
                "single_fact_financial": 1,
                "single_fact_macro": 0,
                "single_fact_fred": 0,
            },
            "derived_quotas": {
                key: 0
                for key in [
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
            },
        }
    }
    report = build_qa(
        db,
        config,
        kg_build_id=kg_build,
        output_dir=str(tmp_path / "audit"),
        batch_size=10,
    )
    assert report["quality"]["passed_count"] == 1
    assert report["split"]["passed_sample_count"] == 1
    qa_build_id = report["qa_build_id"]
    sample = dict(
        db.fetchone("SELECT * FROM qa_samples WHERE qa_build_id = ?", (qa_build_id,))
    )
    assert sample["validation_status"] == "passed"
    assert "Apple Inc." in sample["question"]
    assert float(json.loads(sample["answer_value"])["value"]) == 383285
    exported = export_qa_jsonl(db, qa_build_id, str(tmp_path / "exports"))
    assert exported["sample_count"] == 1
    assert all(
        (tmp_path / "exports" / qa_build_id / name).exists()
        for name in ["benchmark.jsonl", "sft.jsonl", "trace_seeds.jsonl"]
    )
    db.close()
