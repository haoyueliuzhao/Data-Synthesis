from __future__ import annotations

import json
from pathlib import Path

import pytest

from finraw.db.client import MetadataDB
from finraw.qa.export import export_qa_jsonl
from finraw.qa.pipeline import (
    _answer_text,
    _answers_match,
    _complex_split,
    _derived_candidate,
    _evidence_components,
    _git_commit_sha,
    _git_worktree_dirty,
    _recompute,
    _rubric,
    _validate_source_fact_coverage,
    _with_scope_inputs,
    build_qa,
    split_qa_samples,
)


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


def test_complex_split_policy_keeps_training_and_eval_buckets():
    assert _complex_split(0) == "train_complex"
    assert _complex_split(69) == "train_complex"
    assert _complex_split(70) == "dev_complex"
    assert _complex_split(79) == "dev_complex"
    assert _complex_split(80) == "test_complex"
    assert _complex_split(99) == "test_complex"


def _cluster_for_bucket(prefix: str, low: int, high: int) -> str:
    import hashlib

    for index in range(10_000):
        candidate = f"{prefix}_{index}"
        bucket = int(hashlib.sha1(candidate.encode("utf-8")).hexdigest()[:8], 16) % 100
        if low <= bucket <= high:
            return candidate
    raise AssertionError(f"No cluster found for bucket range {low}-{high}")


def _insert_split_candidate_and_sample(
    db,
    qa_build_id: str,
    candidate_id: str,
    qa_id: str,
    cluster_id: str,
    task_subtype: str,
    entity_ids: list[str] | None = None,
    time_scope: dict | None = None,
) -> None:
    entity_ids = entity_ids or ["AAPL_US"]
    time_scope = time_scope or {"year": 2023, "basis": "fiscal_year"}
    db.execute(
        """
        INSERT INTO qa_candidates (
            candidate_id, stable_candidate_id, qa_build_id, task_family,
            task_subtype, difficulty, entity_ids, metric_ids, time_scope,
            entity_scope, source_fact_ids, source_derived_ids, source_document_ids,
            raw_object_ids, canonical_semantics, derived_payload,
            recomputed_payload, answer_payload, kg_path, eligibility_status,
            rejection_reasons
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            candidate_id,
            candidate_id,
            qa_build_id,
            "scope_comparison" if task_subtype == "ranking" else "single_fact",
            task_subtype,
            "medium",
            json.dumps(entity_ids),
            json.dumps(["revenue"]),
            json.dumps(time_scope),
            json.dumps({"entity_id": entity_ids[0]}),
            json.dumps(["fact_1"]),
            json.dumps([]),
            json.dumps([]),
            json.dumps(["raw_1"]),
            json.dumps({"time_scope": time_scope, "entity_ids": entity_ids}),
            json.dumps({}),
            json.dumps({}),
            json.dumps({"value": "1", "unit": "million USD"}),
            json.dumps({"node_ids": ["fact:fact_1@@kg_1"], "edge_ids": []}),
            "eligible",
            json.dumps([]),
        ),
    )
    db.execute(
        """
        INSERT INTO qa_samples (
            qa_id, stable_qa_id, qa_group_id, semantic_cluster_id, qa_build_id,
            candidate_id, task_family, task_subtype, difficulty, language,
            question, canonical_question, answer_type, answer_value, answer_text,
            rubric, source_metadata, generation_method, validation_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            qa_id,
            qa_id,
            f"group_{qa_id}",
            cluster_id,
            qa_build_id,
            candidate_id,
            "scope_comparison" if task_subtype == "ranking" else "single_fact",
            task_subtype,
            "medium",
            "en",
            "Question?",
            "Question?",
            "number",
            json.dumps({"value": "1", "unit": "million USD"}),
            "1 million USD",
            json.dumps({"match_type": "value"}),
            json.dumps({}),
            "deterministic_template",
            "passed",
        ),
    )


def test_semantic_cluster_samples_never_cross_splits(tmp_path):
    db, _, _ = _qa_fixture(tmp_path)
    qa_build_id = "qa_split_same_cluster"
    notes = {"policy": {"temporal_split": {"cutoff_year": 3000}, "quality_gate": {"minimum_overall_pass_rate": 1.0}}}
    db.execute(
        "INSERT INTO qa_builds (qa_build_id, kg_build_id, graph_schema_version, status, sample_count, quality_status, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (qa_build_id, "kg_1", "3.0", "validated", 2, "passed", json.dumps(notes)),
    )
    cluster = _cluster_for_bucket("shared_cluster", 0, 69)
    _insert_split_candidate_and_sample(db, qa_build_id, "cand_a", "qa_a", cluster, "single_fact")
    _insert_split_candidate_and_sample(db, qa_build_id, "cand_b", "qa_b", cluster, "single_fact")

    report = split_qa_samples(db, qa_build_id, output_dir=str(tmp_path / "audit"))
    rows = db.fetchall("SELECT split FROM qa_samples WHERE qa_build_id = ? ORDER BY qa_id", (qa_build_id,))
    splits = {row["split"] for row in rows}
    assert len(splits) == 1
    assert report["semantic_cluster_count"] == 1
    db.close()


def test_complex_tasks_reach_train_dev_and_test_splits(tmp_path):
    db, _, _ = _qa_fixture(tmp_path)
    qa_build_id = "qa_split_complex"
    notes = {"policy": {"temporal_split": {"cutoff_year": 3000}, "quality_gate": {"minimum_overall_pass_rate": 1.0}}}
    db.execute(
        "INSERT INTO qa_builds (qa_build_id, kg_build_id, graph_schema_version, status, sample_count, quality_status, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (qa_build_id, "kg_1", "3.0", "validated", 3, "passed", json.dumps(notes)),
    )
    clusters = {
        "train_complex": _cluster_for_bucket("complex_train", 0, 69),
        "dev_complex": _cluster_for_bucket("complex_dev", 70, 79),
        "test_complex": _cluster_for_bucket("complex_test", 80, 99),
    }
    for index, (expected_split, cluster) in enumerate(clusters.items()):
        _insert_split_candidate_and_sample(
            db,
            qa_build_id,
            f"cand_complex_{index}",
            f"qa_complex_{index}",
            cluster,
            "ranking",
        )
    report = split_qa_samples(db, qa_build_id, output_dir=str(tmp_path / "audit"))
    assert report["split_counts"] == {"dev_complex": 1, "test_complex": 1, "train_complex": 1}
    db.close()


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
    build_row = dict(db.fetchone("SELECT notes FROM qa_builds WHERE qa_build_id = ?", (qa_build_id,)))
    build_notes = json.loads(build_row["notes"])
    assert build_notes["generation"] == "graph_path_driven_deterministic"
    assert build_notes["generator_version"]
    assert build_notes["template_manifest_hash"]
    assert "git_worktree_dirty" in build_notes
    assert build_notes["task_counts"] == {"single_fact": 1}
    assert build_notes["emitted_task_counts"] == {"single_fact": 1}
    sample = dict(
        db.fetchone("SELECT * FROM qa_samples WHERE qa_build_id = ?", (qa_build_id,))
    )
    assert sample["validation_status"] == "passed"
    assert sample["template_id"]
    assert sample["template_hash"]
    assert "Apple Inc." in sample["question"]
    assert float(json.loads(sample["answer_value"])["value"]) == 383285
    evidence = dict(
        db.fetchone("SELECT * FROM qa_evidence_paths WHERE qa_id = ?", (sample["qa_id"],))
    )
    evidence_edges = json.loads(evidence["evidence_edges"])
    evidence_components = json.loads(evidence["evidence_components"])
    assert evidence_edges
    assert {"edge_id", "src", "relation", "dst"} <= set(evidence_edges[0])
    assert len(evidence_components) == 1
    assert json.loads(evidence["evidence_node_ids"]) == json.loads(
        evidence["ordered_node_ids"]
    )
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
    trace_path = Path(exported["files"]["trace_seeds"]["train"]["path"])
    trace_row = json.loads(trace_path.read_text().splitlines()[0])
    assert trace_row["kg_path"]["node_ids"]
    assert trace_row["evidence_subgraph"]["edges"]
    assert trace_row["evidence_subgraph"]["components"]
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


def test_ranking_rubric_requires_ranked_values_and_unit():
    rubric = _rubric(
        {"task_subtype": "ranking"},
        {
            "table": [
                {"rank": 1, "entity_id": "A", "value": 10},
                {"rank": 2, "entity_id": "B", "value": 9},
            ],
            "unit": "million USD",
            "tolerance": "0",
        },
    )
    assert rubric == {
        "match_type": "ranked_table",
        "target_rows": [
            {"rank": 1, "entity_id": "A", "value": 10},
            {"rank": 2, "entity_id": "B", "value": 9},
        ],
        "unit": "million USD",
        "value_tolerance": "0.001",
        "order_required": True,
        "allow_extra_entities": False,
        "allow_missing_entities": False,
    }


def test_screening_rubric_remains_set_match():
    rubric = _rubric(
        {"task_subtype": "multi_condition_screening"},
        {"table": [{"entity_id": "A"}, {"entity_id": "B"}]},
    )
    assert rubric["match_type"] == "set_match"
    assert rubric["target_entity_ids"] == ["A", "B"]
    assert "target_rows" not in rubric


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



def _insert_scope_fact(db, fact_id: str, entity_id: str, value: str) -> None:
    db.execute(
        """
        INSERT INTO standardized_facts (
            fact_id, stable_fact_id, build_id, is_active, entity_id, metric_id,
            normalized_value, normalized_unit, normalized_currency, period_end,
            fiscal_year, fiscal_quarter, time_basis, metric_period_type,
            source_definition_id, source_id, raw_object_id, verification_status,
            graph_ready, graph_ready_reason, is_forecast, confidence_score
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            fact_id,
            fact_id,
            "facts_1",
            1,
            entity_id,
            "revenue",
            value,
            "million USD",
            "USD",
            "2023-12-31",
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
            0.9,
        ),
    )


def test_share_candidate_rejects_kg_derived_output_mismatch(tmp_path):
    db, kg_build, _ = _qa_fixture(tmp_path)
    _insert_scope_fact(db, "fact_msft", "MSFT_US", "100000")
    row = {
        "derived_id": "derived_share_bad",
        "stable_derived_id": "derived_share_bad",
        "derived_type": "share",
        "input_fact_ids": ["fact_1"],
        "entity_scope": {"entity_id": "AAPL_US"},
        "metric_scope": {"metric_id": "revenue"},
        "time_scope": {"basis": "fiscal_year", "year": 2023},
        "scope_type": "configured_company_universe",
        "scope_id": "sec_us_test",
        "scope_definition": "test universe",
        "scope_entity_ids": ["AAPL_US", "MSFT_US"],
        "output_value": "1",
        "output_table": [],
        "unit": "percent",
        "tolerance": "0.000001",
        "calculation_code": "share_of_scope_total",
    }
    scoped = _with_scope_inputs(db, {"input_fact_build_id": "facts_1"}, row, {})
    assert scoped["output_value"] == "1"
    assert scoped["derived_payload"]["value"] == "1"
    assert scoped["recomputed_payload"]["value"] != "1"
    assert scoped["derived_recompute_match"] is False

    candidate = _derived_candidate(
        db,
        scoped,
        "qa_build_test",
        kg_build,
        {"AAPL_US": "Apple Inc.", "MSFT_US": "Microsoft Corp."},
        {"revenue": "revenue"},
        {"fact_1": "raw_1", "fact_msft": "raw_1"},
    )
    assert candidate["answer_payload"] == scoped["recomputed_payload"]
    assert candidate["derived_payload"] == scoped["derived_payload"]
    assert "qa_recompute_mismatch" in candidate["rejection_reasons"]
    db.close()


def test_industry_ranking_expands_full_scope_before_top_k_check(tmp_path):
    db, kg_build, _ = _qa_fixture(tmp_path)
    _insert_scope_fact(db, "fact_msft", "MSFT_US", "390000")
    _insert_scope_fact(db, "fact_goog", "GOOG_US", "500000")
    row = {
        "derived_id": "derived_industry_rank_bad",
        "stable_derived_id": "derived_industry_rank_bad",
        "derived_type": "industry_ranking",
        "input_fact_ids": ["fact_msft", "fact_1"],
        "entity_scope": {"industry": "technology"},
        "metric_scope": {"metric_id": "revenue"},
        "time_scope": {"basis": "fiscal_year", "year": 2023},
        "scope_type": "industry_universe",
        "scope_id": "industry_technology",
        "scope_definition": "all technology entities in the test graph",
        "scope_entity_ids": ["AAPL_US", "MSFT_US", "GOOG_US"],
        "output_value": None,
        "output_table": [
            {"rank": 1, "entity_id": "MSFT_US", "value": 390000},
            {"rank": 2, "entity_id": "AAPL_US", "value": 383285},
        ],
        "unit": "million USD",
        "tolerance": "0.000001",
        "calculation_code": "industry_top_k_desc",
    }
    scoped = _with_scope_inputs(db, {"input_fact_build_id": "facts_1"}, row, {})
    assert scoped["industry_ranking_scope_complete"] is True
    assert set(scoped["input_fact_ids"]) == {"fact_1", "fact_msft", "fact_goog"}
    assert scoped["recomputed_payload"]["table"][:2] == [
        {"rank": 1, "entity_id": "GOOG_US", "value": 500000, "fact_id": "fact_goog"},
        {"rank": 2, "entity_id": "MSFT_US", "value": 390000, "fact_id": "fact_msft"},
    ]
    assert scoped["derived_recompute_match"] is False

    candidate = _derived_candidate(
        db,
        scoped,
        "qa_build_test",
        kg_build,
        {
            "AAPL_US": "Apple Inc.",
            "MSFT_US": "Microsoft Corp.",
            "GOOG_US": "Alphabet Inc.",
        },
        {"revenue": "revenue"},
        {"fact_1": "raw_1", "fact_msft": "raw_1", "fact_goog": "raw_1"},
    )
    assert "qa_recompute_mismatch" in candidate["rejection_reasons"]
    db.close()


def test_share_candidate_accepts_complete_matching_scope(tmp_path):
    db, kg_build, _ = _qa_fixture(tmp_path)
    _insert_scope_fact(db, "fact_msft", "MSFT_US", "383285")
    row = {
        "derived_id": "derived_share_good",
        "stable_derived_id": "derived_share_good",
        "derived_type": "share",
        "input_fact_ids": ["fact_1"],
        "entity_scope": {"entity_id": "AAPL_US"},
        "metric_scope": {"metric_id": "revenue"},
        "time_scope": {"basis": "fiscal_year", "year": 2023},
        "scope_type": "configured_company_universe",
        "scope_id": "sec_us_test",
        "scope_definition": "test universe",
        "scope_entity_ids": ["AAPL_US", "MSFT_US"],
        "output_value": "50",
        "output_table": [],
        "unit": "percent",
        "tolerance": "0.000001",
        "calculation_code": "share_of_scope_total",
    }
    scoped = _with_scope_inputs(db, {"input_fact_build_id": "facts_1"}, row, {})
    assert scoped["share_scope_complete"] is True
    assert scoped["derived_recompute_match"] is True
    assert scoped["input_fact_ids"] == ["fact_1", "fact_msft"]
    candidate = _derived_candidate(
        db,
        scoped,
        "qa_build_test",
        kg_build,
        {"AAPL_US": "Apple Inc.", "MSFT_US": "Microsoft Corp."},
        {"revenue": "revenue"},
        {"fact_1": "raw_1", "fact_msft": "raw_1"},
    )
    assert candidate["eligibility_status"] == "eligible"
    assert candidate["rejection_reasons"] == []
    assert float(candidate["answer_payload"]["value"]) == 50.0
    db.close()


def test_industry_ranking_expands_more_than_ten_entities_for_top_k(tmp_path):
    db, _, _ = _qa_fixture(tmp_path)
    scope_entity_ids = ["AAPL_US"]
    for index in range(11):
        entity_id = f"E{index:02d}_US"
        scope_entity_ids.append(entity_id)
        _insert_scope_fact(db, f"fact_e{index:02d}", entity_id, str(400000 + index))
    expected_top = [
        {"rank": rank, "entity_id": f"E{index:02d}_US", "value": 400000 + index}
        for rank, index in enumerate(range(10, 0, -1), start=1)
    ]
    row = {
        "derived_id": "derived_industry_rank_12",
        "stable_derived_id": "derived_industry_rank_12",
        "derived_type": "industry_ranking",
        "input_fact_ids": ["fact_1"],
        "entity_scope": {"industry": "test"},
        "metric_scope": {"metric_id": "revenue"},
        "time_scope": {"basis": "fiscal_year", "year": 2023},
        "scope_type": "industry_universe",
        "scope_id": "industry_test",
        "scope_definition": "12-entity industry universe",
        "scope_entity_ids": scope_entity_ids,
        "output_value": None,
        "output_table": expected_top,
        "unit": "million USD",
        "tolerance": "0.000001",
        "calculation_code": "industry_top_k_desc",
    }
    scoped = _with_scope_inputs(db, {"input_fact_build_id": "facts_1"}, row, {})
    assert scoped["industry_ranking_scope_complete"] is True
    assert len(scoped["input_fact_ids"]) == 12
    assert len(scoped["recomputed_payload"]["table"]) == 10
    assert [row["entity_id"] for row in scoped["recomputed_payload"]["table"]] == [
        row["entity_id"] for row in expected_top
    ]
    assert scoped["derived_recompute_match"] is True
    db.close()


def test_source_fact_coverage_fails_when_declared_fact_is_not_in_evidence():
    kg_build_id = "kg_1"
    path = {
        "evidence_node_ids": [
            f"entity:AAPL_US@@{kg_build_id}",
            f"fact:fact_1@@{kg_build_id}",
            f"metric:revenue@@{kg_build_id}",
            f"time:2023-FY@@{kg_build_id}",
            f"source:sec_companyfacts@@{kg_build_id}",
        ]
    }
    path_edges = [
        {"src_node_id": f"entity:AAPL_US@@{kg_build_id}", "dst_node_id": f"fact:fact_1@@{kg_build_id}", "relation_type": "HAS_FACT"},
        {"src_node_id": f"fact:fact_1@@{kg_build_id}", "dst_node_id": f"metric:revenue@@{kg_build_id}", "relation_type": "MEASURES"},
        {"src_node_id": f"fact:fact_1@@{kg_build_id}", "dst_node_id": f"time:2023-FY@@{kg_build_id}", "relation_type": "IN_PERIOD"},
        {"src_node_id": f"fact:fact_1@@{kg_build_id}", "dst_node_id": f"source:sec_companyfacts@@{kg_build_id}", "relation_type": "FROM_SOURCE"},
    ]
    ok, detail = _validate_source_fact_coverage(
        {"source_fact_ids": ["fact_1", "fact_missing"]}, path, path_edges, kg_build_id
    )
    assert not ok
    assert detail["missing_fact_nodes"] == ["fact_missing"]
    assert detail["missing_fact_relations"]["fact_missing"] == [
        "FROM_SOURCE",
        "HAS_FACT",
        "IN_PERIOD",
        "MEASURES",
    ]


def test_evidence_components_detect_disconnected_subgraphs():
    components = _evidence_components(
        ["node_a", "node_b", "node_c", "node_d"],
        [
            {"edge_id": "edge_ab", "src": "node_a", "relation": "REL", "dst": "node_b"},
            {"edge_id": "edge_cd", "src": "node_c", "relation": "REL", "dst": "node_d"},
        ],
    )
    assert len(components) == 2
    assert {tuple(component["node_ids"]) for component in components} == {
        ("node_a", "node_b"),
        ("node_c", "node_d"),
    }


def test_git_metadata_helpers_use_repo_root_cwd(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert _git_commit_sha() != "unknown"
    assert _git_worktree_dirty() in {True, False}
