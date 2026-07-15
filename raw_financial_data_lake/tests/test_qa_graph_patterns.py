from __future__ import annotations

from decimal import Decimal

from finraw.db.client import MetadataDB
from finraw.qa.difficulty import assess_difficulty, graph_features
from finraw.qa.diversity import build_qa_diversity_report
from finraw.qa.graph_patterns import get_pattern, pattern_registry
from finraw.qa.operators import OperatorError, execute_operator
from finraw.qa.pipeline import build_qa
from finraw.qa.plans import execute_plan


def _insert_node(db, build_id, stable_id, node_type, source_pk):
    node_id = f"{stable_id}@@{build_id}"
    db.execute(
        "INSERT INTO kg_nodes (node_id, stable_node_id, kg_build_id, node_type, source_pk, is_active) VALUES (?, ?, ?, ?, ?, ?)",
        (node_id, stable_id, build_id, node_type, source_pk, 1),
    )
    return node_id


def _insert_edge(db, build_id, stable_id, src, dst, relation):
    db.execute(
        "INSERT INTO kg_edges (edge_id, stable_edge_id, kg_build_id, src_node_id, dst_node_id, relation_type, is_active) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (f"{stable_id}@@{build_id}", stable_id, build_id, src, dst, relation, 1),
    )


def _graph_fixture(tmp_path):
    db = MetadataDB(str(tmp_path / "graph_qa.db"))
    db.init_schema()
    kg_build = "kg_graph_1"
    fact_build = "facts_graph_1"
    entity_build = "entities_graph_1"
    metric_build = "metrics_graph_1"
    db.execute(
        "INSERT INTO source_registry (source_id, source_name, source_type, authority_level) VALUES (?, ?, ?, ?)",
        ("sec_companyfacts", "SEC", "api", "S1_official"),
    )
    db.execute(
        "INSERT INTO raw_objects (raw_object_id, source_id, object_type, storage_uri, original_url, content_sha256, validation_status) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("raw_graph", "sec_companyfacts", "json", "raw.json", "https://example.test/raw", "hash", "passed"),
    )
    for entity_id, name in [("A_US", "Company A"), ("B_US", "Company B")]:
        db.execute(
            "INSERT INTO canonical_entities (entity_id, canonical_name, entity_type, build_id, is_active) VALUES (?, ?, ?, ?, ?)",
            (entity_id, name, "company", entity_build, 1),
        )
    for metric_id, name in [("revenue", "Revenue"), ("net_income", "Net Income")]:
        db.execute(
            "INSERT INTO metrics (metric_id, canonical_name, metric_category, period_type, build_id, is_active) VALUES (?, ?, ?, ?, ?, ?)",
            (metric_id, name, "financial_statement", "period_flow", metric_build, 1),
        )
        db.execute(
            "INSERT INTO source_metric_definitions (definition_id, source_id, metric_id, raw_concept_name, build_id, is_active) VALUES (?, ?, ?, ?, ?, ?)",
            (f"def_{metric_id}", "sec_companyfacts", metric_id, metric_id, "definitions_1", 1),
        )
    db.execute(
        "INSERT INTO kg_builds (kg_build_id, graph_schema_version, input_fact_build_id, input_qa_build_id, input_entity_build_id, input_metric_build_id, input_source_definition_build_id, status, quality_status, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (kg_build, "3.0", fact_build, "derived_1", entity_build, metric_build, "definitions_1", "success", "passed", 1),
    )

    entity_nodes = {
        entity_id: _insert_node(db, kg_build, f"entity:{entity_id}", "Entity", entity_id)
        for entity_id in ["A_US", "B_US"]
    }
    metric_nodes = {
        metric_id: _insert_node(db, kg_build, f"metric:{metric_id}", "Metric", metric_id)
        for metric_id in ["revenue", "net_income"]
    }
    period_nodes = {
        year: _insert_node(db, kg_build, f"time:{year}-FY", "TimePeriod", f"{year}-FY")
        for year in [2021, 2022, 2023]
    }
    source_node = _insert_node(db, kg_build, "source:sec_companyfacts", "DataSource", "sec_companyfacts")
    raw_node = _insert_node(db, kg_build, "raw_object:raw_graph", "RawObject", "raw_graph")
    definition_nodes = {
        metric_id: _insert_node(db, kg_build, f"source_definition:def_{metric_id}", "SourceDefinition", f"def_{metric_id}")
        for metric_id in ["revenue", "net_income"]
    }
    values = {
        "A_US": {"revenue": {2021: 100, 2022: 120, 2023: 150}, "net_income": {2021: 10, 2022: 20, 2023: 30}},
        "B_US": {"revenue": {2021: 90, 2022: 130, 2023: 140}},
    }
    for entity_id, metrics in values.items():
        for metric_id, yearly in metrics.items():
            for year, value in yearly.items():
                fact_id = f"fact_{entity_id}_{metric_id}_{year}"
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
                    (fact_id, fact_id, fact_build, 1, entity_id, metric_id, str(value), "million USD", "USD", f"{year}-12-31", year, "FY", "fiscal_year", "period_flow", f"def_{metric_id}", "sec_companyfacts", "raw_graph", "single_source", 1, "ready", 0),
                )
                fact_node = _insert_node(db, kg_build, f"fact:{fact_id}", "Fact", fact_id)
                edges = [
                    (entity_nodes[entity_id], fact_node, "HAS_FACT"),
                    (fact_node, metric_nodes[metric_id], "MEASURES"),
                    (fact_node, period_nodes[year], "IN_PERIOD"),
                    (fact_node, source_node, "FROM_SOURCE"),
                    (fact_node, raw_node, "TRACED_TO"),
                    (fact_node, definition_nodes[metric_id], "USES_SOURCE_DEFINITION"),
                ]
                for index, (src, dst, relation) in enumerate(edges):
                    _insert_edge(db, kg_build, f"edge_{fact_id}_{index}", src, dst, relation)
    config = {
        "qa": {
            "quotas": {"single_fact_financial": 0, "single_fact_worldbank": 0, "single_fact_imf": 0, "single_fact_fred": 0},
            "derived_quotas": {},
            "graph_patterns": {
                "enabled": True,
                "quotas": {
                    "pairwise_entity_metric_comparison": 1,
                    "entity_cross_metric_comparison": 1,
                    "entity_metric_temporal_average": 1,
                },
            },
            "temporal_split": {"cutoff_year": 3000},
            "quality_gate": {"minimum_overall_pass_rate": 1.0, "critical_tasks": {}, "max_critical_check_failures": 0},
        }
    }
    return db, kg_build, config


def test_pattern_registry_separates_pattern_plan_and_answer_schema():
    registry = pattern_registry()
    pattern = get_pattern("pairwise_entity_metric_comparison")
    assert len(registry) >= 5
    assert pattern.operator_template["operators"][0]["operator"] == "compare"
    assert pattern.answer_schema["type"] == "comparison"


def test_operation_plan_replays_intermediate_results():
    facts = {
        "a": {"fact_id": "a", "entity_id": "A", "normalized_value": "100", "normalized_unit": "million USD", "normalized_currency": "USD"},
        "b": {"fact_id": "b", "entity_id": "B", "normalized_value": "125", "normalized_unit": "million USD", "normalized_currency": "USD"},
    }
    plan = {"operators": [{"step_id": "answer", "operator": "compare", "inputs": [{"binding": "left"}, {"binding": "right"}]}], "output_step": "answer"}
    execution = execute_plan(plan, {"left": "a", "right": "b"}, facts)
    assert execution.status == "passed"
    assert execution.output["winner_id"] == "B"
    assert Decimal(execution.output["difference"]) == Decimal("25")
    assert execution.intermediate_results[0]["operator"] == "compare"


def test_operator_rejects_incompatible_units():
    left = {"normalized_value": "1", "normalized_unit": "USD", "normalized_currency": "USD"}
    right = {"normalized_value": "1", "normalized_unit": "percent", "normalized_currency": None}
    try:
        execute_operator("compare", [left, right])
    except OperatorError as exc:
        assert "Incompatible units" in str(exc)
    else:
        raise AssertionError("Expected incompatible units to be rejected")


def test_difficulty_uses_graph_and_operation_features():
    features = graph_features(
        source_fact_ids=[f"f{i}" for i in range(12)],
        source_derived_ids=["d1"],
        entity_ids=["A", "B", "C"],
        metric_ids=["revenue", "margin"],
        facts=[{"fiscal_year": year, "source_id": "sec"} for year in range(2019, 2024)],
        evidence={"node_ids": ["a", "b", "c"], "edge_ids": ["e1", "e2"], "evidence_edges": [{"src": "a", "dst": "b"}, {"src": "b", "dst": "c"}]},
        operation_plan={"operators": [{"step_id": "filter", "operator": "filter", "inputs": [{"binding": "facts"}]}, {"step_id": "rank", "operator": "rank", "inputs": [{"step": "filter"}]}], "output_step": "rank"},
        answer_payload={"table": [{"entity_id": "A"}, {"entity_id": "B"}]},
    )
    level, score = assess_difficulty(features)
    assert features["operation_depth"] == 2
    assert level in {"hard", "expert", "research"}
    assert score > 5


def test_graph_pattern_build_discovers_and_validates_multi_hop_qa(tmp_path):
    db, kg_build, config = _graph_fixture(tmp_path)
    report = build_qa(db, config, kg_build_id=kg_build, output_dir=str(tmp_path / "audit"), batch_size=10)
    assert report["candidate"]["eligible_candidate_count"] == 3
    assert report["quality"]["passed_count"] == 3
    assert report["split"]["build_gate_status"] == "passed"
    rows = db.fetchall(
        "SELECT pattern_id, operation_plan_id, difficulty_score FROM qa_candidates WHERE qa_build_id = ? ORDER BY pattern_id",
        (report["qa_build_id"],),
    )
    assert {row["pattern_id"] for row in rows} == {
        "pairwise_entity_metric_comparison",
        "entity_cross_metric_comparison",
        "entity_metric_temporal_average",
    }
    assert all(row["operation_plan_id"] and row["difficulty_score"] for row in rows)
    checks = db.fetchall(
        "SELECT check_name, check_status FROM qa_quality_checks WHERE qa_build_id = ? AND check_name LIKE 'operator%'",
        (report["qa_build_id"],),
    )
    assert checks
    assert all(row["check_status"] == "passed" for row in checks)
    analysis = build_qa_diversity_report(
        db, report["qa_build_id"], output_dir=str(tmp_path / "analysis")
    )
    assert analysis["semantic_diversity"]["unique_graph_patterns"] == 3
    assert analysis["semantic_diversity"]["unique_operation_plans"] == 2
    assert analysis["kg_utilization"]["fact_node_utilization"] > 0
    assert analysis["kg_utilization"]["edge_type_coverage"] > 0
