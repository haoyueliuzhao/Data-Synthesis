from __future__ import annotations

import copy
import json
from decimal import Decimal

import pytest

from finraw.db.client import MetadataDB
from finraw.qa.difficulty import assess_difficulty, graph_features
from finraw.qa.diversity import build_qa_diversity_report
from finraw.qa.comparability import annual_duration_valid, latest_contiguous_window, metric_pair_allowed, comparability_policy
from finraw.qa.graph_matcher import discover_pattern_matches
from finraw.qa.graph_patterns import get_pattern, pattern_registry
from finraw.qa.operators import OperatorError, execute_operator
from finraw.qa.pattern_compiler import (
    compile_logical_pattern,
    compile_pattern_proposal,
    compile_proposal_matches,
)
from finraw.qa.pattern_mining import (
    _deduplicate_facts,
    _mine_scope_rank_followup,
    _select_metric_pool,
    _series_groups,
    _stratified_fact_sample,
    load_approved_proposals,
    mine_qa_patterns,
    mining_policy,
    review_pattern_proposal,
    transition_mining_run,
)
from finraw.qa.pipeline import (
    _latest_year,
    _match_time_scope,
    _scope_is_complete,
    build_qa,
    validate_qa_samples,
)
from finraw.qa.plans import execute_plan
from finraw.qa.semantic_constraints import validate_semantic_constraints
from finraw.qa.verbalizer import realize_question, validate_question_roundtrip


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
            "INSERT INTO canonical_entities (entity_id, canonical_name, entity_type, industry, build_id, is_active) VALUES (?, ?, ?, ?, ?, ?)",
            (entity_id, name, "company", "Technology", entity_build, 1),
        )
    for metric_id, name in [("revenue", "Revenue"), ("net_income", "Net Income")]:
        db.execute(
            "INSERT INTO metrics (metric_id, canonical_name, metric_category, statement_type, period_type, build_id, is_active) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (metric_id, name, "financial_statement", "income_statement", "period_flow", metric_build, 1),
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
                        normalized_value, normalized_unit, normalized_currency, period_start, period_end,
                        fiscal_year, fiscal_quarter, time_basis, metric_period_type,
                        source_definition_id, source_id, raw_object_id, verification_status,
                        graph_ready, graph_ready_reason, is_forecast, frequency,
                        seasonal_adjustment, vintage_policy, comparability_level
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (fact_id, fact_id, fact_build, 1, entity_id, metric_id, str(value), "million USD", "USD", f"{year}-01-01", f"{year}-12-31", year, "FY", "fiscal_year", "period_flow", f"def_{metric_id}", "sec_companyfacts", "raw_graph", "single_source", 1, "ready", 0, "annual", "not_applicable", "latest_filing", "strict"),
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
                    "temporal_argmax_then_metric_lookup": 1,
                },
            },
            "temporal_split": {"cutoff_year": 3000},
            "quality_gate": {"minimum_overall_pass_rate": 1.0, "critical_tasks": {}, "max_critical_check_failures": 0},
        }
    }
    return db, kg_build, config


def _approve_mining_run(db, mining_run_id):
    transition_mining_run(
        db,
        mining_run_id,
        target_status="reviewed",
        reviewer="test-reviewer",
    )
    return transition_mining_run(
        db,
        mining_run_id,
        target_status="approved_for_qa",
        reviewer="test-approver",
    )


def test_pattern_registry_separates_pattern_plan_and_answer_schema():
    registry = pattern_registry()
    pattern = get_pattern("pairwise_entity_metric_comparison")
    assert len(registry) >= 5
    assert pattern.operator_template["operators"][0]["operator"] == "compare"
    assert pattern.answer_schema["type"] == "comparison"
    assert pattern.matcher == "pairwise_entity_metric_comparison"
    assert get_pattern("temporal_argmax_then_metric_lookup").pattern_version == 4


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


def test_ranked_secondary_lookup_rejects_mixed_units_and_currencies():
    ranking = {
        "table": [
            {"rank": 1, "entity_id": "A", "value": "100"},
            {"rank": 2, "entity_id": "B", "value": "90"},
        ],
        "unit": "million USD",
        "currency": "USD",
    }
    secondary = [
        {
            "fact_id": "a_assets",
            "entity_id": "A",
            "normalized_value": "200",
            "normalized_unit": "million USD",
            "normalized_currency": "USD",
        },
        {
            "fact_id": "b_assets",
            "entity_id": "B",
            "normalized_value": "180",
            "normalized_unit": "USD",
            "normalized_currency": "USD",
        },
    ]
    try:
        execute_operator("lookup_ranked_entities", [ranking, secondary])
    except OperatorError as exc:
        assert "Incompatible units" in str(exc)
    else:
        raise AssertionError("Expected mixed secondary units to be rejected")

    secondary[1]["normalized_unit"] = "million USD"
    secondary[1]["normalized_currency"] = "CNY"
    try:
        execute_operator("lookup_ranked_entities", [ranking, secondary])
    except OperatorError as exc:
        assert "Incompatible currencies" in str(exc)
    else:
        raise AssertionError("Expected mixed secondary currencies to be rejected")


def test_metric_pair_policy_and_temporal_continuity_are_explicit():
    policy = comparability_policy()
    assert metric_pair_allowed("revenue", "net_income", policy)
    assert not metric_pair_allowed("revenue", "total_assets", policy)
    rows = [
        {"fact_id": "f2020", "fiscal_year": 2020},
        {"fact_id": "f2022", "fiscal_year": 2022},
        {"fact_id": "f2023", "fiscal_year": 2023},
    ]
    assert latest_contiguous_window(
        rows, frequency="annual", minimum=3, maximum=5, require_contiguous=True
    ) == []
    assert annual_duration_valid(
        {
            "frequency": "annual",
            "metric_period_type": "period_flow",
            "period_start": "2022-01-01",
            "period_end": "2022-12-31",
        }
    )
    assert not annual_duration_valid(
        {
            "frequency": "annual",
            "metric_period_type": "period_flow",
            "period_start": "2022-10-01",
            "period_end": "2022-12-31",
        }
    )


def test_semantic_constraint_validator_executes_metric_roles_and_compatibility():
    def fact(fact_id, metric_id, *, vintage="latest_filing", period_type="period_flow"):
        return {
            "fact_id": fact_id,
            "entity_id": "A_US",
            "entity_type": "company",
            "metric_id": metric_id,
            "source_id": "sec_companyfacts",
            "source_definition_id": f"def_{metric_id}",
            "normalized_value": "100",
            "normalized_unit": "million USD",
            "normalized_currency": "USD",
            "graph_ready": 1,
            "is_forecast": 0,
            "frequency": "annual",
            "time_basis": "fiscal_year",
            "metric_period_type": period_type,
            "seasonal_adjustment": "not_applicable",
            "vintage_policy": vintage,
            "comparability_level": "strict",
            "financial_scope_type": "consolidated_entity",
        }

    ontology = {
        "revenue": {"metric_id": "revenue", "statement_type": "income_statement", "period_type": "period_flow"},
        "net_income": {"metric_id": "net_income", "statement_type": "income_statement", "period_type": "period_flow"},
        "total_assets": {"metric_id": "total_assets", "statement_type": "balance_sheet", "period_type": "point_in_time"},
    }
    policy = comparability_policy()
    cross = get_pattern("entity_cross_metric_comparison")
    allowed_facts = {
        "r": fact("r", "revenue"),
        "n": fact("n", "net_income"),
    }
    allowed = validate_semantic_constraints(
        cross,
        {"fact_ids": ["r", "n"], "input_bindings": {"left": "r", "right": "n"}, "metric_ids": ["revenue", "net_income"]},
        allowed_facts,
        ontology,
        policy,
    )
    assert allowed.passed

    disallowed_facts = {
        "r": fact("r", "revenue"),
        "a": fact("a", "total_assets", period_type="point_in_time"),
    }
    disallowed = validate_semantic_constraints(
        cross,
        {"fact_ids": ["r", "a"], "input_bindings": {"left": "r", "right": "a"}, "metric_ids": ["revenue", "total_assets"]},
        disallowed_facts,
        ontology,
        policy,
    )
    assert "registered_comparable_metric_pair" in disallowed.errors
    assert "same_statement_type" in disallowed.errors
    assert "same_period_type" in disallowed.errors

    vintage_mismatch = dict(allowed_facts)
    vintage_mismatch["n"] = fact("n", "net_income", vintage="initial_release")
    mismatch = validate_semantic_constraints(
        cross,
        {"fact_ids": ["r", "n"], "metric_ids": ["revenue", "net_income"]},
        vintage_mismatch,
        ontology,
        policy,
    )
    assert "same_vintage_policy" in mismatch.errors
    assert "source_definition_compatibility" in mismatch.errors

    followup = get_pattern("temporal_argmax_then_metric_lookup")
    reversed_roles = validate_semantic_constraints(
        followup,
        {
            "fact_ids": ["r", "n"],
            "metric_ids": ["net_income", "revenue"],
            "primary_metric_id": "net_income",
            "secondary_metric_id": "revenue",
        },
        allowed_facts,
        ontology,
        policy,
    )
    assert "registered_followup_metric_pair" in reversed_roles.errors


def test_temporal_series_key_separates_every_comparability_dimension():
    def fact(fact_id, year, **overrides):
        row = {
            "fact_id": fact_id,
            "entity_id": "A_US",
            "metric_id": "revenue",
            "source_id": "sec_companyfacts",
            "source_definition_id": "def_revenue",
            "frequency": "annual",
            "time_basis": "fiscal_year",
            "metric_period_type": "period_flow",
            "financial_scope_type": "consolidated_entity",
            "normalized_unit": "million USD",
            "normalized_currency": "USD",
            "seasonal_adjustment": "not_applicable",
            "vintage_policy": "latest_filing",
            "comparability_level": "strict",
            "fiscal_year": year,
            "fiscal_quarter": "FY",
            "period_end": f"{year}-12-31",
            "is_forecast": 0,
        }
        row.update(overrides)
        return row

    rows = [fact(f"base_{year}", year) for year in [2021, 2022, 2023]]
    rows.extend(
        [
            fact("definition", 2022, source_definition_id="def_revenue_v2"),
            fact("unit", 2022, normalized_unit="USD"),
            fact("currency", 2022, normalized_currency="CNY"),
            fact("seasonal", 2022, seasonal_adjustment="seasonally_adjusted"),
            fact("vintage", 2022, vintage_policy="initial_release"),
            fact("comparability", 2022, comparability_level="comparable"),
            fact("period_type", 2022, metric_period_type="point_in_time"),
        ]
    )
    groups = _series_groups(rows)
    assert len(groups) == 8
    assert sorted(len(values) for values in groups.values()) == [1] * 7 + [3]

    duplicate = fact("zz_duplicate", 2022)
    deduplicated = _deduplicate_facts([*rows, duplicate])
    assert len(deduplicated) == len(rows)
    assert "base_2022" in {row["fact_id"] for row in deduplicated}
    assert "zz_duplicate" not in {row["fact_id"] for row in deduplicated}


def test_automatic_scope_mining_requires_strict_complete_case_universe():
    def fact(entity_id, metric_id, value):
        return {
            "fact_id": f"{entity_id}_{metric_id}",
            "entity_id": entity_id,
            "entity_scope_id": entity_id,
            "entity_type": "company",
            "industry": "Technology",
            "metric_id": metric_id,
            "source_id": "sec_companyfacts",
            "source_definition_id": f"def_{metric_id}",
            "normalized_value": str(value),
            "normalized_unit": "million USD",
            "normalized_currency": "USD",
            "graph_ready": 1,
            "is_forecast": 0,
            "frequency": "annual",
            "time_basis": "fiscal_year",
            "metric_period_type": "period_flow",
            "financial_scope_type": "consolidated_entity",
            "seasonal_adjustment": "not_applicable",
            "vintage_policy": "latest_filing",
            "comparability_level": "strict",
            "fiscal_year": 2023,
            "fiscal_quarter": "FY",
            "period_start": "2023-01-01",
            "period_end": "2023-12-31",
        }

    rows = []
    for index, entity_id in enumerate(["A_US", "B_US", "C_US"], start=1):
        rows.append(fact(entity_id, "revenue", 100 * index))
        rows.append(fact(entity_id, "net_income", 10 * index))
    metrics = {
        "revenue": {
            "metric_id": "revenue",
            "statement_type": "income_statement",
            "period_type": "period_flow",
        },
        "net_income": {
            "metric_id": "net_income",
            "statement_type": "income_statement",
            "period_type": "period_flow",
        },
    }
    policy = mining_policy(
        {
            "qa": {
                "pattern_mining": {
                    "minimum_scope_entities": 3,
                    "max_bindings_per_proposal": 10,
                }
            }
        }
    )
    semantic_policy = comparability_policy()

    def accepted(candidate_rows):
        return [
            item
            for item in _mine_scope_rank_followup(
                candidate_rows, metrics, policy, semantic_policy
            )
            if item["support_count"] > 0
        ]

    valid = accepted(rows)
    assert len(valid) == 1
    assert valid[0]["metric_ids"] == ["revenue", "net_income"]
    assert valid[0]["support_count"] == 1
    binding = valid[0]["binding_validation_records"][0]["binding"]
    assert binding["scope_input_coverage"] == 1.0
    assert binding["financial_scope"]["entity_scope_ids"] == [
        "A_US",
        "B_US",
        "C_US",
    ]
    fact_map = {row["fact_id"]: row for row in rows}
    semantic_result = validate_semantic_constraints(
        valid[0]["pattern_spec"],
        binding,
        fact_map,
        metrics,
        semantic_policy,
    )
    assert semantic_result.passed

    tampered = copy.deepcopy(fact_map)
    tampered["A_US_net_income"]["normalized_unit"] = "USD"
    semantic_result = validate_semantic_constraints(
        valid[0]["pattern_spec"],
        binding,
        tampered,
        metrics,
        semantic_policy,
    )
    assert "secondary_unit_consistent" in semantic_result.errors

    mutations = [
        ("A_US", "revenue", "normalized_unit", "USD"),
        ("A_US", "net_income", "normalized_currency", "CNY"),
        ("A_US", "net_income", "source_definition_id", "def_net_income_v2"),
        ("A_US", "net_income", "comparability_level", "comparable"),
        ("A_US", "net_income", "entity_scope_id", "A_SEGMENT"),
        ("A_US", "net_income", "fiscal_quarter", "Q4"),
        ("A_US", "net_income", "period_start", "2023-10-01"),
        ("A_US", "net_income", "is_forecast", 1),
    ]
    for entity_id, metric_id, field, value in mutations:
        changed = copy.deepcopy(rows)
        target = next(
            row
            for row in changed
            if row["entity_id"] == entity_id and row["metric_id"] == metric_id
        )
        target[field] = value
        assert accepted(changed) == [], field

    duplicated = copy.deepcopy(rows)
    duplicate = copy.deepcopy(
        next(
            row
            for row in duplicated
            if row["entity_id"] == "A_US" and row["metric_id"] == "net_income"
        )
    )
    duplicate["fact_id"] = "A_US_net_income_duplicate"
    duplicated.append(duplicate)
    assert accepted(duplicated) == []


def test_temporal_argmax_then_lookup_replays_two_steps():
    facts = {}
    for year, revenue, income in [(2021, 100, 10), (2022, 140, 12), (2023, 120, 15)]:
        facts[f"r{year}"] = {
            "fact_id": f"r{year}", "metric_id": "revenue",
            "normalized_value": str(revenue), "normalized_unit": "USD",
            "normalized_currency": "USD", "fiscal_year": year, "time_basis": "fiscal_year",
        }
        facts[f"n{year}"] = {
            "fact_id": f"n{year}", "metric_id": "net_income",
            "normalized_value": str(income), "normalized_unit": "USD",
            "normalized_currency": "USD", "fiscal_year": year, "time_basis": "fiscal_year",
        }
    pattern = get_pattern("temporal_argmax_then_metric_lookup")
    execution = execute_plan(
        pattern.operator_template,
        {
            "primary_series": ["r2021", "r2022", "r2023"],
            "secondary_series": ["n2021", "n2022", "n2023"],
        },
        facts,
    )
    assert execution.status == "passed"
    assert execution.output["result_period"] == 2022
    assert Decimal(execution.output["primary_value"]) == Decimal("140")
    assert Decimal(execution.output["secondary_value"]) == Decimal("12")
    assert len(execution.intermediate_results) == 2


def test_scope_operation_plans_replay_filter_rank_lookup_and_screening():
    facts = {}
    current_values = {
        "A": (120, 12, 100, 40),
        "B": (130, 26, 200, 100),
        "C": (115, Decimal("17.25"), 150, 75),
        "D": (105, Decimal("26.25"), 100, 20),
    }
    previous_values = {"A": 100, "B": 100, "C": 100, "D": 100}
    for entity_id, (revenue, income, assets, liabilities) in current_values.items():
        for metric_id, value in {
            "revenue": revenue,
            "net_income": income,
            "total_assets": assets,
            "total_liabilities": liabilities,
        }.items():
            fact_id = f"{entity_id}_{metric_id}_2023"
            facts[fact_id] = {
                "fact_id": fact_id,
                "entity_id": entity_id,
                "normalized_value": str(value),
                "normalized_unit": "million USD",
                "normalized_currency": "USD",
            }
        fact_id = f"{entity_id}_revenue_2022"
        facts[fact_id] = {
            "fact_id": fact_id,
            "entity_id": entity_id,
            "normalized_value": str(previous_values[entity_id]),
            "normalized_unit": "million USD",
            "normalized_currency": "USD",
        }
    entities = sorted(current_values)
    bindings = {
        "current_revenue": [f"{key}_revenue_2023" for key in entities],
        "previous_revenue": [f"{key}_revenue_2022" for key in entities],
        "net_income": [f"{key}_net_income_2023" for key in entities],
        "total_assets": [f"{key}_total_assets_2023" for key in entities],
        "total_liabilities": [f"{key}_total_liabilities_2023" for key in entities],
        "revenue": [f"{key}_revenue_2023" for key in entities],
    }
    filter_rank = execute_plan(
        get_pattern("industry_growth_filter_then_margin_rank").operator_template,
        bindings,
        facts,
    )
    assert filter_rank.status == "passed"
    assert [row["entity_id"] for row in filter_rank.output["table"]] == ["B", "C", "A"]
    assert len(filter_rank.intermediate_results) == 5

    rank_lookup = execute_plan(
        get_pattern("industry_revenue_rank_then_assets_lookup").operator_template,
        bindings,
        facts,
    )
    assert rank_lookup.status == "passed"
    assert rank_lookup.output["table"][0] == {
        "rank": 1,
        "entity_id": "B",
        "primary_value": "130",
        "secondary_value": "200",
    }

    screening = execute_plan(
        get_pattern("industry_multi_factor_screening").operator_template,
        bindings,
        facts,
    )
    assert screening.status == "passed"
    assert [row["entity_id"] for row in screening.output["table"]] == ["B"]
    assert len(screening.intermediate_results) == 4


def test_temporal_followup_rejects_cross_financial_scope(tmp_path):
    db, kg_build, config = _graph_fixture(tmp_path)
    db.execute(
        "UPDATE standardized_facts SET entity_scope_id = ?, financial_scope_type = ? "
        "WHERE entity_id = ? AND metric_id = ?",
        ("A_US_SEGMENT", "segment", "A_US", "net_income"),
    )
    kg = dict(
        db.fetchone("SELECT * FROM kg_builds WHERE kg_build_id = ?", (kg_build,))
    )
    matches = discover_pattern_matches(
        db,
        kg,
        "temporal_argmax_then_metric_lookup",
        limit=20,
        policy=config["qa"]["graph_patterns"].get("comparability"),
    )
    assert matches == []


def test_graph_matchers_exclude_forecast_facts(tmp_path):
    db, kg_build, config = _graph_fixture(tmp_path)
    forecast_id = "fact_B_US_revenue_2023"
    db.execute(
        "UPDATE standardized_facts SET is_forecast = 1 WHERE fact_id = ?",
        (forecast_id,),
    )
    kg = dict(
        db.fetchone("SELECT * FROM kg_builds WHERE kg_build_id = ?", (kg_build,))
    )
    matches = discover_pattern_matches(
        db,
        kg,
        "pairwise_entity_metric_comparison",
        limit=20,
        policy=config["qa"]["graph_patterns"].get("comparability"),
    )
    assert matches
    assert all(forecast_id not in match["fact_ids"] for match in matches)


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
        semantic_constraint_count=5,
    )
    level, score = assess_difficulty(features)
    assert features["operation_depth"] == 2
    assert features["semantic_constraint_count"] == 5
    assert level in {"hard", "expert", "research"}
    assert score > 5


def test_graph_pattern_build_discovers_and_validates_multi_hop_qa(tmp_path):
    db, kg_build, config = _graph_fixture(tmp_path)
    report = build_qa(db, config, kg_build_id=kg_build, output_dir=str(tmp_path / "audit"), batch_size=10)
    assert report["candidate"]["eligible_candidate_count"] == 4
    assert report["quality"]["passed_count"] == 4
    assert report["split"]["build_gate_status"] == "passed"
    rows = db.fetchall(
        "SELECT pattern_id, pattern_hash, operation_plan_id, operation_plan_hash, difficulty_score FROM qa_candidates WHERE qa_build_id = ? ORDER BY pattern_id",
        (report["qa_build_id"],),
    )
    assert {row["pattern_id"] for row in rows} == {
        "pairwise_entity_metric_comparison",
        "entity_cross_metric_comparison",
        "entity_metric_temporal_average",
        "temporal_argmax_then_metric_lookup",
    }
    assert all(
        row["pattern_hash"]
        and row["operation_plan_id"]
        and row["operation_plan_hash"]
        and row["difficulty_score"]
        for row in rows
    )
    build = db.fetchone(
        "SELECT pattern_manifest_hash, operator_manifest_hash, difficulty_policy_hash FROM qa_builds WHERE qa_build_id = ?",
        (report["qa_build_id"],),
    )
    assert all(build[column] for column in build.keys())
    active_versions = db.fetchall(
        "SELECT pattern_id, pattern_version FROM qa_graph_patterns "
        "WHERE pattern_id = 'pairwise_entity_metric_comparison' AND is_active = 1"
    )
    assert [(row["pattern_id"], row["pattern_version"]) for row in active_versions] == [
        ("pairwise_entity_metric_comparison", 3)
    ]
    checks = db.fetchall(
        "SELECT check_name, check_status FROM qa_quality_checks WHERE qa_build_id = ? AND check_name LIKE 'operator%'",
        (report["qa_build_id"],),
    )
    assert checks
    assert all(row["check_status"] == "passed" for row in checks)
    analysis = build_qa_diversity_report(
        db, report["qa_build_id"], output_dir=str(tmp_path / "analysis")
    )
    assert analysis["semantic_diversity"]["unique_graph_patterns"] == 4
    assert analysis["semantic_diversity"]["unique_operation_plans"] == 3
    assert analysis["funnels"]["validated_samples"]["sample_count"] == 4
    assert analysis["funnels"]["exported_samples"]["sample_count"] == 4
    assert analysis["semantic_diversity"]["unique_operator_dags"] == 4
    assert analysis["kg_utilization"]["fact_node_utilization"] > 0
    assert analysis["kg_utilization"]["edge_type_coverage"] > 0


def test_smoke_build_can_pass_without_replacing_active_qa(tmp_path):
    db, kg_build, config = _graph_fixture(tmp_path)
    report = build_qa(
        db,
        config,
        kg_build_id=kg_build,
        output_dir=str(tmp_path / "audit_non_active"),
        batch_size=10,
        activate=False,
    )
    build = db.fetchone(
        "SELECT status, is_active FROM qa_builds WHERE qa_build_id = ?",
        (report["qa_build_id"],),
    )
    assert report["split"]["build_gate_status"] == "passed"
    assert report["split"]["activated"] is False
    assert build["status"] == "ready"
    assert not bool(build["is_active"])


def test_pattern_mining_discovers_scores_and_compiles_executable_motifs(tmp_path):
    db, kg_build, config = _graph_fixture(tmp_path)
    config["qa"]["pattern_mining"] = {
        "enabled": True,
        "auto_run": False,
        "min_support": 1,
        "min_total_score": 0,
        "max_metrics": 8,
        "rows_per_metric": 100,
        "max_proposals": 30,
        "max_bindings_per_proposal": 5,
        "minimum_heldout_bindings": 0,
        "minimum_scope_entities": 2,
    }
    report = mine_qa_patterns(
        db,
        config,
        kg_build_id=kg_build,
        output_dir=str(tmp_path / "mining"),
    )
    assert report["proposal_count"] >= 3
    assert report["approved_count"] == report["proposal_count"]
    assert report["run_status"] == "success"
    with pytest.raises(RuntimeError, match="expected approved_for_qa"):
        load_approved_proposals(
            db, kg_build, report["mining_run_id"], limit=100
        )
    approved_run = _approve_mining_run(db, report["mining_run_id"])
    assert approved_run["status"] == "approved_for_qa"
    assert [event["stage"] for event in approved_run["lifecycle_events"]] == [
        "running",
        "success",
        "reviewed",
        "approved_for_qa",
    ]
    proposals = load_approved_proposals(
        db, kg_build, report["mining_run_id"], limit=100
    )
    families = {proposal["motif_family"] for proposal in proposals}
    assert {
        "cross_metric_comparison",
        "temporal_aggregation",
        "temporal_extrema_followup",
    }.issubset(families)
    cross_proposals = [
        item for item in proposals if item["motif_family"] == "cross_metric_comparison"
    ]
    assert cross_proposals
    cross = cross_proposals[0]
    assert cross["status"] == "published"
    assert cross["proposal_semantic_id"].startswith("qapatsem_")
    assert cross["proposal_snapshot_id"].startswith("qapatsnap_")
    assert cross["static_pattern_id"] == "entity_cross_metric_comparison"
    assert cross["binding_mode"] == "known_pattern_binding"
    assert compile_pattern_proposal(cross).pattern_version == get_pattern(
        "entity_cross_metric_comparison"
    ).pattern_version
    assert cross["heldout_bindings"]
    assert cross["example_binding_pass_rate"] == 1.0
    assert cross["heldout_binding_pass_rate"] == 1.0
    assert cross["operation_execution_pass_rate"] == 1.0
    assert 0.0 <= cross["static_pattern_overlap"] <= 1.0
    assert 0.0 <= cross["binding_diversity_score"] <= 1.0
    assert [event["stage"] for event in cross["lifecycle_events"]] == [
        "proposed",
        "semantic_validated",
        "execution_validated",
        "reviewed_approved",
        "published",
    ]
    assert all(
        set(item["pattern_spec"]["node_constraints"][2]["values"])
        == {"revenue", "net_income"}
        for item in cross_proposals
    )
    followup_proposals = [
        item for item in proposals if item["motif_family"] == "temporal_extrema_followup"
    ]
    assert all(
        item["pattern_spec"]["node_constraints"][2]["values"]
        == ["revenue", "net_income"]
        for item in followup_proposals
    )
    assert all(
        item["pattern_spec"]["semantic_validation"]["accepted_binding_count"]
        == item["support_count"]
        for item in proposals
    )
    motif_rows = db.fetchall(
        "SELECT * FROM qa_graph_motif_observations WHERE mining_run_id = ?",
        (report["mining_run_id"],),
    )
    assert len(motif_rows) == 5
    assert {row["motif_family"] for row in motif_rows} == {
        "derived_fact_composition", "entity_set_scope", "time_hierarchy",
        "fact_provenance", "cross_source_reconciliation",
    }
    assert report["graph_native_motifs"]["observation_count"] == 5
    proposal = next(
        item
        for item in proposals
        if item["motif_family"] == "temporal_extrema_followup"
    )
    pattern = compile_pattern_proposal(proposal)
    kg = dict(
        db.fetchone("SELECT * FROM kg_builds WHERE kg_build_id = ?", (kg_build,))
    )
    compile_policy = {
        **mining_policy(config),
        "semantic_policy": comparability_policy(),
    }
    matches = compile_proposal_matches(
        db,
        kg,
        proposal,
        qa_build_id="qa_compile_test",
        limit=1,
        policy=compile_policy,
    )
    match = matches[0]
    assert match["binding_source"] == "compiled_query"
    assert match["compiled_binding_id"]
    assert match["pattern_compilation_id"]
    facts = {
        row["fact_id"]: dict(row)
        for row in db.fetchall(
            "SELECT * FROM standardized_facts WHERE fact_id IN ("
            + ",".join("?" for _ in match["fact_ids"])
            + ")",
            match["fact_ids"],
        )
    }
    execution = execute_plan(
        pattern.operator_template, match["input_bindings"], facts
    )
    assert execution.status == "passed"
    assert len(execution.intermediate_results) == 2
    assert proposal["proposal_hash"] == match["pattern_proposal_hash"]


def test_logical_compiler_rediscovers_and_persists_production_bindings(tmp_path):
    db, kg_build, config = _graph_fixture(tmp_path)
    config["qa"]["pattern_mining"] = {
        "enabled": True,
        "auto_run": False,
        "families": ["cross_metric_comparison"],
        "min_support": 1,
        "min_total_score": 0,
        "max_metrics": 8,
        "rows_per_metric": 100,
        "max_proposals": 10,
        "max_bindings_per_proposal": 1,
        "minimum_heldout_bindings": 0,
        "max_candidates_per_proposal": 3,
        "compiled_scan_rows_per_metric": 1000,
        "compiled_scan_multiplier": 20,
        "compiled_max_per_stratum": 4,
    }
    mining = mine_qa_patterns(db, config, kg_build_id=kg_build)
    _approve_mining_run(db, mining["mining_run_id"])
    proposal = load_approved_proposals(
        db, kg_build, mining["mining_run_id"], limit=10
    )[0]
    proposal = copy.deepcopy(proposal)
    proposal["binding_examples"] = [
        {
            "fact_ids": ["audit-only-fact"],
            "input_bindings": {"left": "audit-only-fact"},
        }
    ]
    proposal["heldout_bindings"] = []
    kg = dict(
        db.fetchone("SELECT * FROM kg_builds WHERE kg_build_id = ?", (kg_build,))
    )
    policy = {
        **mining_policy(config),
        "semantic_policy": comparability_policy(),
    }
    logical_plan = compile_logical_pattern(proposal, kg, policy)
    assert logical_plan.target_kg_build_id == kg_build
    assert set(logical_plan.metric_ids) == {"revenue", "net_income"}
    assert logical_plan.sampling["audit_examples_are_inputs"] is False

    matches = compile_proposal_matches(
        db,
        kg,
        proposal,
        qa_build_id="qa_compiled_bindings_test",
        limit=3,
        policy=policy,
    )
    assert len(matches) == 3
    assert all("audit-only-fact" not in row["fact_ids"] for row in matches)
    assert all(row["binding_source"] == "compiled_query" for row in matches)
    compilation = db.fetchone(
        "SELECT * FROM qa_pattern_compilations WHERE compilation_id = ?",
        (matches[0]["pattern_compilation_id"],),
    )
    assert compilation["status"] == "success"
    assert compilation["compiled_binding_count"] == 3
    assert compilation["discovered_binding_count"] >= 3
    stored = db.fetchall(
        "SELECT * FROM qa_compiled_bindings WHERE compilation_id = ?",
        (matches[0]["pattern_compilation_id"],),
    )
    assert len(stored) == 3
    assert all(row["execution_status"] == "passed" for row in stored)


def test_pattern_proposal_requires_execution_validation_and_manual_publication(
    tmp_path,
):
    db, kg_build, config = _graph_fixture(tmp_path)
    config["qa"]["pattern_mining"] = {
        "enabled": True,
        "auto_run": False,
        "families": ["cross_metric_comparison"],
        "min_support": 1,
        "min_total_score": 0,
        "max_metrics": 8,
        "rows_per_metric": 100,
        "max_proposals": 10,
        "max_bindings_per_proposal": 5,
        "minimum_heldout_bindings": 1,
        "require_manual_review": True,
    }
    report = mine_qa_patterns(db, config, kg_build_id=kg_build)
    assert report["published_count"] == 0
    proposal = dict(
        db.fetchone(
            "SELECT * FROM qa_pattern_proposals WHERE mining_run_id = ?",
            (report["mining_run_id"],),
        )
    )
    assert proposal["status"] == "execution_validated"
    assert proposal["manual_review_status"] == "pending"
    assert proposal["example_binding_pass_rate"] == 1.0
    assert proposal["heldout_binding_pass_rate"] >= 0.99
    with pytest.raises(RuntimeError, match="expected approved_for_qa"):
        load_approved_proposals(
            db, kg_build, report["mining_run_id"], limit=10
        )
    with pytest.raises(ValueError, match="Only published"):
        compile_pattern_proposal(proposal)

    reviewed = review_pattern_proposal(
        db,
        proposal["proposal_id"],
        decision="approve",
        reviewer="qa-reviewer",
        notes="bindings and semantics reviewed",
        publish=False,
    )
    assert reviewed["status"] == "reviewed_approved"
    assert reviewed["manual_review_status"] == "approved"
    with pytest.raises(RuntimeError, match="expected approved_for_qa"):
        load_approved_proposals(
            db, kg_build, report["mining_run_id"], limit=10
        )
    reviewed = review_pattern_proposal(
        db,
        proposal["proposal_id"],
        decision="approve",
        reviewer="qa-publisher",
    )
    assert reviewed["status"] == "published"
    _approve_mining_run(db, report["mining_run_id"])
    assert load_approved_proposals(
        db, kg_build, report["mining_run_id"], limit=10
    )[0]["status"] == "published"


def test_pattern_proposal_execution_failure_cannot_be_published(tmp_path):
    db, kg_build, config = _graph_fixture(tmp_path)
    db.execute(
        "UPDATE standardized_facts SET normalized_value = 'not-a-number' "
        "WHERE metric_id = 'net_income'"
    )
    config["qa"]["pattern_mining"] = {
        "enabled": True,
        "auto_run": False,
        "families": ["cross_metric_comparison"],
        "min_support": 1,
        "min_total_score": 0,
        "max_metrics": 8,
        "rows_per_metric": 100,
        "max_proposals": 10,
        "max_bindings_per_proposal": 5,
        "minimum_heldout_bindings": 1,
    }
    report = mine_qa_patterns(db, config, kg_build_id=kg_build)
    assert report["published_count"] == 0
    proposal = dict(
        db.fetchone(
            "SELECT * FROM qa_pattern_proposals WHERE mining_run_id = ?",
            (report["mining_run_id"],),
        )
    )
    assert proposal["status"] == "semantic_validated"
    assert proposal["operation_execution_pass_rate"] == 0.0
    assert proposal["example_binding_pass_rate"] == 0.0
    assert "binding_example_execution_failed" in json.loads(
        proposal["rejection_reasons"]
    )
    assert (
        db.fetchone(
            "SELECT COUNT(*) AS count FROM qa_pattern_proposals "
            "WHERE mining_run_id = ? AND status = 'published'",
            (report["mining_run_id"],),
        )["count"]
        == 0
    )


def test_pattern_mining_does_not_join_temporal_definition_changes(tmp_path):
    db, kg_build, config = _graph_fixture(tmp_path)
    db.execute(
        "UPDATE standardized_facts "
        "SET source_definition_id = source_definition_id || '_v2' "
        "WHERE metric_id = 'revenue' AND fiscal_year = 2022"
    )
    config["qa"]["pattern_mining"] = {
        "enabled": True,
        "auto_run": False,
        "families": ["temporal_aggregation"],
        "min_support": 1,
        "min_total_score": 0,
        "max_metrics": 8,
        "rows_per_metric": 100,
        "max_proposals": 10,
        "max_bindings_per_proposal": 5,
        "minimum_heldout_bindings": 0,
        "minimum_temporal_observations": 3,
        "maximum_temporal_observations": 5,
        "require_contiguous_periods": True,
    }
    report = mine_qa_patterns(db, config, kg_build_id=kg_build)
    assert report["approved_count"] == 1
    _approve_mining_run(db, report["mining_run_id"])
    proposals = load_approved_proposals(
        db, kg_build, report["mining_run_id"], limit=10
    )
    assert len(proposals) == 1
    assert proposals[0]["pattern_spec"]["node_constraints"][2]["values"] == [
        "net_income"
    ]


class _QuestionProvider:
    def __init__(self, question):
        self.question = question
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        return [self.question]


def test_controlled_llm_verbalizer_preserves_slots_and_never_receives_answer():
    canonical = "Compare Company A and Company B on Revenue in fiscal year 2023."
    slots = {
        "entity_a": "Company A",
        "entity_b": "Company B",
        "metric": "Revenue",
        "period": "fiscal year 2023",
    }
    question = (
        "For fiscal year 2023, compare Company A and Company B using Revenue."
    )
    provider = _QuestionProvider({
        "question": question,
        "slot_map": slots,
        "operator_id": "comparison",
        "constraints": [],
    })
    result = realize_question(
        canonical,
        semantics={"operation": "comparison"},
        immutable_slots=slots,
        required_slots=list(slots),
        config={"mode": "controlled_llm", "variants": 2},
        provider=provider,
    )
    assert result.question == question
    assert result.generation_method == "controlled_llm"
    assert result.validation["passed"]
    assert "answer" not in str(provider.requests[0]).lower()
    assert result.validation["answer_exposed_to_generator"] is False


def test_controlled_llm_verbalizer_rejects_semantic_slot_loss():
    canonical = "What was Company A's Revenue for fiscal year 2023?"
    result = realize_question(
        canonical,
        semantics={"operation": "lookup"},
        immutable_slots={
            "entity": "Company A",
            "metric": "Revenue",
            "period": "fiscal year 2023",
        },
        required_slots=["entity", "metric", "period"],
        config={"mode": "controlled_llm"},
        provider=_QuestionProvider("How did the company perform?"),
    )
    assert result.question == canonical
    assert result.generation_method == "deterministic_template_fallback"
    assert result.validation["fallback_reason"] == "no_llm_variant_passed_slot_roundtrip"


def test_structured_roundtrip_rejects_operator_or_constraint_changes():
    contract = {
        "slot_map": {"scope": "the technology industry", "top_k": "3"},
        "required_slots": ["scope", "top_k"],
        "operator_id": "filter_then_rank",
        "constraints": [
            {"position": 0, "step_id": "screen", "operator": "filter", "params": {"op": "gt", "value": 10}},
            {"position": 1, "step_id": "rank", "operator": "rank", "params": {"direction": "desc", "top_k": 3}},
        ],
    }
    variant = {
        "question": "Within the technology industry, rank the top 3 companies.",
        "slot_map": contract["slot_map"],
        "operator_id": "rank_then_filter",
        "constraints": list(reversed(contract["constraints"])),
    }
    result = validate_question_roundtrip(variant, contract)
    assert not result["passed"]
    assert "operator_id_mismatch" in result["contract_errors"]
    assert "constraints_mismatch" in result["contract_errors"]


def test_scope_completeness_requires_exact_entity_set():
    semantics = {"entity_ids": ["A_US", "B_US", "C_US"]}
    assert _scope_is_complete(
        "filter_then_rank", semantics, ["C_US", "A_US", "B_US"]
    )
    assert not _scope_is_complete(
        "filter_then_rank", semantics, ["A_US", "B_US", "D_US"]
    )
    assert not _scope_is_complete(
        "filter_then_rank", semantics, ["A_US", "B_US"]
    )


def test_mined_quarter_period_has_structured_scope_and_split_year():
    scope = _match_time_scope({"period": "2026 Q1", "frequency": "quarterly"})
    assert scope == {
        "fiscal_year": 2026,
        "fiscal_quarter": "Q1",
        "basis": "fiscal_year",
        "frequency": "quarterly",
    }
    assert _latest_year(scope) == 2026
    assert _latest_year({"year": "2026 Q1"}) == 2026


def test_qa_build_requires_and_persists_explicit_approved_mining_run(tmp_path):
    db, kg_build, config = _graph_fixture(tmp_path)
    config["qa"]["graph_patterns"]["enabled"] = False
    config["qa"]["pattern_mining"] = {
        "enabled": True,
        "auto_run": False,
        "min_support": 1,
        "min_total_score": 0,
        "max_metrics": 8,
        "rows_per_metric": 100,
        "max_proposals": 10,
        "max_bindings_per_proposal": 2,
        "minimum_heldout_bindings": 0,
        "max_candidates_per_proposal": 1,
        "minimum_scope_entities": 2,
    }
    mining = mine_qa_patterns(db, config, kg_build_id=kg_build)
    mining_run_id = mining["mining_run_id"]

    with pytest.raises(ValueError, match="explicit mining_run_id"):
        build_qa(
            db,
            config,
            kg_build_id=kg_build,
            output_dir=str(tmp_path / "missing_pin"),
            activate=False,
        )
    with pytest.raises(RuntimeError, match="expected approved_for_qa"):
        build_qa(
            db,
            config,
            kg_build_id=kg_build,
            mining_run_id=mining_run_id,
            output_dir=str(tmp_path / "unapproved"),
            activate=False,
        )

    _approve_mining_run(db, mining_run_id)
    with pytest.raises(ValueError, match="belongs to"):
        load_approved_proposals(
            db, "kg_different", mining_run_id, limit=10
        )
    report = build_qa(
        db,
        config,
        kg_build_id=kg_build,
        mining_run_id=mining_run_id,
        output_dir=str(tmp_path / "pinned"),
        batch_size=10,
        activate=False,
    )
    build = db.fetchone(
        "SELECT mining_run_id, notes FROM qa_builds WHERE qa_build_id = ?",
        (report["qa_build_id"],),
    )
    assert build["mining_run_id"] == mining_run_id
    notes = json.loads(build["notes"])
    assert notes["pattern_mining"]["selected_run"]["mining_run_id"] == mining_run_id


def test_new_approved_mining_run_supersedes_old_without_latest_fallback(tmp_path):
    db, kg_build, config = _graph_fixture(tmp_path)
    config["qa"]["pattern_mining"] = {
        "enabled": True,
        "auto_run": False,
        "families": ["cross_metric_comparison"],
        "min_support": 1,
        "min_total_score": 0,
        "max_metrics": 8,
        "rows_per_metric": 100,
        "max_proposals": 10,
        "max_bindings_per_proposal": 2,
        "minimum_heldout_bindings": 0,
    }
    first = mine_qa_patterns(db, config, kg_build_id=kg_build)
    first_id = first["mining_run_id"]
    first_proposals = db.fetchall(
        "SELECT proposal_id, proposal_semantic_id, proposal_snapshot_id "
        "FROM qa_pattern_proposals WHERE mining_run_id = ? ORDER BY proposal_semantic_id",
        (first_id,),
    )
    _approve_mining_run(db, first_id)

    second = mine_qa_patterns(db, config, kg_build_id=kg_build)
    second_id = second["mining_run_id"]
    second_proposals = db.fetchall(
        "SELECT proposal_id, proposal_semantic_id, proposal_snapshot_id "
        "FROM qa_pattern_proposals WHERE mining_run_id = ? ORDER BY proposal_semantic_id",
        (second_id,),
    )
    assert [row["proposal_semantic_id"] for row in first_proposals] == [
        row["proposal_semantic_id"] for row in second_proposals
    ]
    assert {row["proposal_id"] for row in first_proposals}.isdisjoint(
        {row["proposal_id"] for row in second_proposals}
    )
    assert load_approved_proposals(db, kg_build, first_id, limit=10)
    with pytest.raises(RuntimeError, match="status=success"):
        load_approved_proposals(db, kg_build, second_id, limit=10)

    _approve_mining_run(db, second_id)
    first_row = db.fetchone(
        "SELECT status, superseded_by_run_id FROM qa_pattern_mining_runs "
        "WHERE mining_run_id = ?",
        (first_id,),
    )
    assert first_row["status"] == "superseded"
    assert first_row["superseded_by_run_id"] == second_id
    with pytest.raises(RuntimeError, match="status=superseded"):
        load_approved_proposals(db, kg_build, first_id, limit=10)
    assert load_approved_proposals(db, kg_build, second_id, limit=10)


def test_mined_patterns_flow_through_candidate_plan_and_verifier(tmp_path):
    db, kg_build, config = _graph_fixture(tmp_path)
    config["qa"]["graph_patterns"]["enabled"] = False
    config["qa"]["pattern_mining"] = {
        "enabled": True,
        "auto_run": True,
        "auto_approve_for_qa": True,
        "min_support": 1,
        "min_total_score": 0,
        "max_metrics": 8,
        "rows_per_metric": 100,
        "max_proposals": 10,
        "max_bindings_per_proposal": 2,
        "minimum_heldout_bindings": 0,
        "max_candidates_per_proposal": 1,
        "minimum_scope_entities": 2,
    }
    report = build_qa(
        db,
        config,
        kg_build_id=kg_build,
        output_dir=str(tmp_path / "mined_build"),
        batch_size=10,
        activate=False,
    )
    assert report["candidate"]["eligible_candidate_count"] >= 3
    assert report["quality"]["rejected_count"] == 0
    assert report["candidate"]["pattern_compilation_summary"][
        "compiled_binding_count"
    ] >= 3
    candidates = db.fetchall(
        "SELECT pattern_id, pattern_proposal_id, pattern_score, "
        "pattern_compilation_id, compiled_binding_id "
        "FROM qa_candidates WHERE qa_build_id = ?",
        (report["qa_build_id"],),
    )
    assert candidates
    assert all(row["pattern_id"] for row in candidates)
    assert all(row["pattern_proposal_id"] for row in candidates)
    assert all(row["pattern_compilation_id"] for row in candidates)
    assert all(row["compiled_binding_id"] for row in candidates)
    proposal_checks = db.fetchall(
        "SELECT check_status FROM qa_quality_checks WHERE qa_build_id = ? "
        "AND check_name = 'pattern_proposal_match'",
        (report["qa_build_id"],),
    )
    assert proposal_checks
    assert all(row["check_status"] == "passed" for row in proposal_checks)
    compiled_checks = db.fetchall(
        "SELECT check_status FROM qa_quality_checks WHERE qa_build_id = ? "
        "AND check_name = 'compiled_binding_match'",
        (report["qa_build_id"],),
    )
    assert compiled_checks
    assert all(row["check_status"] == "passed" for row in compiled_checks)
    semantic_checks = db.fetchall(
        "SELECT check_status FROM qa_quality_checks WHERE qa_build_id = ? "
        "AND check_name = 'semantic_constraint_gate'",
        (report["qa_build_id"],),
    )
    assert semantic_checks
    assert all(row["check_status"] == "passed" for row in semantic_checks)
    candidate_id = db.fetchone(
        "SELECT candidate_id FROM qa_candidates WHERE qa_build_id = ? "
        "ORDER BY candidate_id LIMIT 1",
        (report["qa_build_id"],),
    )["candidate_id"]
    db.execute(
        "UPDATE qa_candidates SET compiled_binding_hash = 'tampered' "
        "WHERE candidate_id = ?",
        (candidate_id,),
    )
    db.execute(
        "UPDATE qa_samples SET validation_status = 'pending' "
        "WHERE candidate_id = ?",
        (candidate_id,),
    )
    validate_qa_samples(db, report["qa_build_id"], batch_size=10)
    tampered_check = db.fetchone(
        "SELECT check_status FROM qa_quality_checks "
        "WHERE qa_build_id = ? AND check_name = 'compiled_binding_match' "
        "AND qa_id IN (SELECT qa_id FROM qa_samples WHERE candidate_id = ?)",
        (report["qa_build_id"], candidate_id),
    )
    assert tampered_check["check_status"] == "failed"


def test_metric_pool_balances_business_value_and_support():
    rows = [
        {"metric_id": "dense_a", "metric_category": "macro", "statement_type": None, "fact_count": 50000},
        {"metric_id": "dense_b", "metric_category": "macro", "statement_type": None, "fact_count": 40000},
        {"metric_id": "valuable_tail", "metric_category": "financial_statement", "statement_type": "income_statement", "fact_count": 12},
    ]
    selected = _select_metric_pool(
        rows,
        {
            "max_metrics": 2,
            "business_value_metric_ids": ("valuable_tail",),
            "business_value_quota_ratio": 0.5,
        },
    )
    assert "valuable_tail" in {row["metric_id"] for row in selected}
    assert len(selected) == 2


def test_fact_pool_sampling_is_stratified_and_deterministic():
    rows = []
    for index, (source, industry, year, frequency) in enumerate([
        ("sec", "Technology", 2018, "annual"),
        ("sec", "Healthcare", 2023, "annual"),
        ("fred", "macro", 2018, "monthly"),
        ("worldbank", "macro", 2023, "annual"),
    ]):
        rows.append(
            {
                "fact_id": f"fact_{index}",
                "metric_category": "financial_statement" if source == "sec" else "macro",
                "statement_type": "income_statement" if source == "sec" else None,
                "source_id": source,
                "industry": industry,
                "entity_type": "company" if source == "sec" else "country",
                "fiscal_year": year,
                "frequency": frequency,
            }
        )
    selected = _stratified_fact_sample(rows, 4, "medium", 5)
    reversed_selected = _stratified_fact_sample(list(reversed(rows)), 4, "medium", 5)
    assert [row["fact_id"] for row in selected] == [
        row["fact_id"] for row in reversed_selected
    ]
    assert {row["source_id"] for row in selected} == {"sec", "fred", "worldbank"}
