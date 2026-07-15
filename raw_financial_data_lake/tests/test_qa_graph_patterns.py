from __future__ import annotations

from decimal import Decimal

from finraw.db.client import MetadataDB
from finraw.qa.difficulty import assess_difficulty, graph_features
from finraw.qa.diversity import build_qa_diversity_report
from finraw.qa.comparability import annual_duration_valid, latest_contiguous_window, metric_pair_allowed, comparability_policy
from finraw.qa.graph_matcher import discover_pattern_matches
from finraw.qa.graph_patterns import get_pattern, pattern_registry
from finraw.qa.operators import OperatorError, execute_operator
from finraw.qa.pattern_compiler import compile_pattern_proposal, compile_proposal_matches
from finraw.qa.pattern_mining import load_approved_proposals, mine_qa_patterns
from finraw.qa.pipeline import _latest_year, _match_time_scope, build_qa
from finraw.qa.plans import execute_plan
from finraw.qa.verbalizer import realize_question


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


def test_pattern_registry_separates_pattern_plan_and_answer_schema():
    registry = pattern_registry()
    pattern = get_pattern("pairwise_entity_metric_comparison")
    assert len(registry) >= 5
    assert pattern.operator_template["operators"][0]["operator"] == "compare"
    assert pattern.answer_schema["type"] == "comparison"
    assert pattern.matcher == "pairwise_entity_metric_comparison"
    assert get_pattern("temporal_argmax_then_metric_lookup").pattern_version == 3


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
    proposals = load_approved_proposals(db, kg_build, limit=100)
    families = {proposal["motif_family"] for proposal in proposals}
    assert {
        "cross_metric_comparison",
        "temporal_aggregation",
        "temporal_extrema_followup",
    }.issubset(families)
    proposal = next(
        item
        for item in proposals
        if item["motif_family"] == "temporal_extrema_followup"
    )
    pattern = compile_pattern_proposal(proposal)
    matches = compile_proposal_matches(proposal, limit=1)
    match = matches[0]
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
    provider = _QuestionProvider(question)
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


def test_mined_patterns_flow_through_candidate_plan_and_verifier(tmp_path):
    db, kg_build, config = _graph_fixture(tmp_path)
    config["qa"]["graph_patterns"]["enabled"] = False
    config["qa"]["pattern_mining"] = {
        "enabled": True,
        "auto_run": True,
        "min_support": 1,
        "min_total_score": 0,
        "max_metrics": 8,
        "rows_per_metric": 100,
        "max_proposals": 10,
        "max_bindings_per_proposal": 2,
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
    candidates = db.fetchall(
        "SELECT pattern_id, pattern_proposal_id, pattern_score "
        "FROM qa_candidates WHERE qa_build_id = ?",
        (report["qa_build_id"],),
    )
    assert candidates
    assert all(str(row["pattern_id"]).startswith("mined_") for row in candidates)
    assert all(row["pattern_proposal_id"] for row in candidates)
    proposal_checks = db.fetchall(
        "SELECT check_status FROM qa_quality_checks WHERE qa_build_id = ? "
        "AND check_name = 'pattern_proposal_match'",
        (report["qa_build_id"],),
    )
    assert proposal_checks
    assert all(row["check_status"] == "passed" for row in proposal_checks)
