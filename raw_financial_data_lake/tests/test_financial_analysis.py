from __future__ import annotations

import json
from pathlib import Path

from finraw.analysis.export import export_analysis_jsonl
from finraw.analysis.peer_scope import scope_membership_hash
from finraw.analysis.pipeline import _load_kg_build, build_financial_analysis
from finraw.analysis.signals import execute_signal
from finraw.analysis.verifier import validate_analysis_samples
from finraw.db.client import MetadataDB

CASH_FLOW = "net_cash_provided_by_used_in_operating_activities"


def _fact(
    fact_id: str, entity_id: str, metric_id: str, year: int, value: float
) -> dict:
    point = metric_id in {"total_assets", "total_liabilities"}
    return {
        "fact_id": fact_id,
        "entity_id": entity_id,
        "entity_scope_id": entity_id,
        "financial_scope_type": "consolidated_entity",
        "metric_id": metric_id,
        "normalized_value": value,
        "normalized_unit": "million USD",
        "normalized_currency": "USD",
        "period_start": f"{year}-01-01",
        "period_end": f"{year}-12-31",
        "fiscal_year": year,
        "fiscal_quarter": "FY",
        "time_basis": "as_of_date" if point else "fiscal_year",
        "metric_period_type": "point_in_time" if point else "period_flow",
        "source_definition_id": f"def_{metric_id}",
        "frequency": "annual",
        "seasonal_adjustment": "not_applicable",
        "vintage_policy": "latest_filing",
        "is_forecast": 0,
        "comparability_level": "strict",
        "source_id": "sec_companyfacts",
        "verification_status": "single_source",
        "graph_ready": 1,
        "confidence_score": 0.98,
    }


def test_signal_executor_detects_earnings_cash_divergence():
    profit = [
        _fact(f"profit_{year}", "A_US", "net_income", year, value)
        for year, value in [(2021, 100), (2022, 110), (2023, 130)]
    ]
    cash = [
        _fact(f"cash_{year}", "A_US", CASH_FLOW, year, value)
        for year, value in [(2021, 100), (2022, 95), (2023, 90)]
    ]
    result = execute_signal(
        "earnings_cash_divergence_v1",
        {"profit_series": profit, "cash_series": cash},
    )
    assert result.direction == "negative"
    assert result.strength == "strong"
    assert result.payload["profit_growth_pct"] == "30.0"
    assert result.payload["cash_growth_pct"] == "-10.0"
    assert result.payload["spread_pct"] == "40.0"


def test_analysis_compiler_builds_three_patterns_and_rejects_tampering(tmp_path):
    db = MetadataDB(str(tmp_path / "analysis.db"))
    db.init_schema()
    kg_build_id = "kg_analysis_fixture"
    fact_build_id = "fact_build_analysis_fixture"
    entity_build_id = "entity_build_analysis_fixture"
    metric_build_id = "metric_build_analysis_fixture"
    db.execute(
        """
        INSERT INTO kg_builds (
            kg_build_id, graph_schema_version, input_fact_build_id,
            input_qa_build_id, input_entity_build_id, input_metric_build_id,
            input_source_definition_build_id, status, quality_status, is_active
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            kg_build_id,
            "3.0",
            fact_build_id,
            "derived_build_fixture",
            entity_build_id,
            metric_build_id,
            "source_definition_build_fixture",
            "success",
            "passed",
            1,
        ),
    )
    assert _load_kg_build(db, None)["kg_build_id"] == kg_build_id
    entities = [f"COMPANY_{index}_US" for index in range(5)]
    for index, entity_id in enumerate(entities):
        db.execute(
            """
            INSERT INTO canonical_entities (
                entity_id, canonical_name, entity_type, market, country,
                currency, industry, build_id, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entity_id,
                f"Company {index}",
                "company",
                "US",
                "US",
                "USD",
                "Technology",
                entity_build_id,
                1,
            ),
        )
        for year_index, year in enumerate((2021, 2022, 2023)):
            values = {
                "revenue": 100 + index * 10 + year_index * (10 + index),
                "net_income": 10 + index + year_index * (2 + index),
                CASH_FLOW: 14 + index - year_index * (1 + (index % 2)),
                "total_assets": 200 + index * 15 + year_index * 12,
                "total_liabilities": 80 + index * 10 + year_index * 8,
            }
            for metric_id, value in values.items():
                fact_id = f"fact_{entity_id}_{metric_id}_{year}"
                row = _fact(fact_id, entity_id, metric_id, year, value)
                columns = ["build_id", *row]
                db.execute(
                    f"INSERT INTO standardized_facts ({','.join(columns)}) "
                    f"VALUES ({','.join('?' for _ in columns)})",
                    [fact_build_id, *[row[column] for column in row]],
                )
                fact_node = f"fact:{fact_id}@@{kg_build_id}"
                entity_node = f"entity:{entity_id}@@{kg_build_id}"
                metric_node = f"metric:{metric_id}@@{kg_build_id}"
                time_node = f"time:{fact_id}@@{kg_build_id}"
                source_node = f"source:sec_companyfacts@@{kg_build_id}"
                for node_id, node_type, source_pk in [
                    (fact_node, "Fact", fact_id),
                    (entity_node, "Entity", entity_id),
                    (metric_node, "Metric", metric_id),
                    (time_node, "TimePeriod", fact_id),
                    (source_node, "DataSource", "sec_companyfacts"),
                ]:
                    db.execute(
                        "INSERT OR IGNORE INTO kg_nodes (node_id, stable_node_id, kg_build_id, node_type, source_pk, is_active) VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            node_id,
                            node_id.split("@@")[0],
                            kg_build_id,
                            node_type,
                            source_pk,
                            1,
                        ),
                    )
                for relation, src, dst in [
                    ("HAS_FACT", entity_node, fact_node),
                    ("MEASURES", fact_node, metric_node),
                    ("IN_PERIOD", fact_node, time_node),
                    ("FROM_SOURCE", fact_node, source_node),
                ]:
                    edge_id = f"edge_{relation}_{fact_id}"
                    db.execute(
                        "INSERT OR IGNORE INTO kg_edges (edge_id, stable_edge_id, kg_build_id, src_node_id, dst_node_id, relation_type, is_active) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (edge_id, edge_id, kg_build_id, src, dst, relation, 1),
                    )
    report = build_financial_analysis(
        db,
        {
            "analysis": {
                "pattern_quotas": {
                    "operating_trend_summary_v1": 2,
                    "growth_quality_diagnosis_v1": 2,
                    "peer_positioning_v1": 2,
                },
                "minimum_pattern_samples": {
                    "operating_trend_summary_v1": 1,
                    "growth_quality_diagnosis_v1": 1,
                    "peer_positioning_v1": 1,
                },
            }
        },
        kg_build_id=kg_build_id,
        output_dir=str(tmp_path / "audit"),
        activate=False,
    )
    assert report["build_gate_status"] == "passed"
    assert report["candidate_count"] == 6
    assert report["quality"]["passed_count"] == 6
    assert report["pattern_counts"] == {
        "growth_quality_diagnosis_v1": 2,
        "operating_trend_summary_v1": 2,
        "peer_positioning_v1": 2,
    }
    assert sum(report["split_counts"].values()) == 6

    peer_candidate = dict(
        db.fetchone(
            "SELECT * FROM analysis_candidates "
            "WHERE analysis_build_id = ? AND analysis_pattern_id = ? "
            "ORDER BY candidate_id LIMIT 1",
            (report["analysis_build_id"], "peer_positioning_v1"),
        )
    )
    peer_bundle = dict(
        db.fetchone(
            "SELECT * FROM analysis_evidence_bundles WHERE evidence_bundle_id = ?",
            (peer_candidate["evidence_bundle_id"],),
        )
    )
    expected_peer_ids = json.loads(peer_candidate["expected_scope_entity_ids"])
    peer_contract = json.loads(peer_candidate["peer_scope_contract"])
    assert expected_peer_ids == entities
    assert peer_contract["expected_scope_entity_ids"] == entities
    assert peer_contract["scope_membership_hash"] == peer_candidate[
        "scope_membership_hash"
    ]
    assert peer_candidate["scope_eligibility_policy_hash"]
    assert json.loads(peer_bundle["expected_scope_entity_ids"]) == entities

    signal_ids = json.loads(peer_candidate["signal_ids"])
    signal_rows = [
        dict(row)
        for row in db.fetchall(
            "SELECT signal_id, operator_plan FROM financial_signal_instances "
            f"WHERE signal_id IN ({','.join('?' for _ in signal_ids)})",
            signal_ids,
        )
    ]
    original_plans = {
        str(row["signal_id"]): str(row["operator_plan"]) for row in signal_rows
    }
    first_plan = json.loads(signal_rows[0]["operator_plan"])
    target_entity_id = str(first_plan["target_entity_id"])
    omitted_entity_id = next(
        entity_id for entity_id in reversed(entities) if entity_id != target_entity_id
    )
    all_role_fact_ids = sorted(
        {
            str(fact_id)
            for row in signal_rows
            for fact_ids in json.loads(row["operator_plan"])["role_fact_ids"].values()
            for fact_id in fact_ids
        }
    )
    fact_entity_rows = db.fetchall(
        "SELECT fact_id, entity_id FROM standardized_facts "
        f"WHERE fact_id IN ({','.join('?' for _ in all_role_fact_ids)})",
        all_role_fact_ids,
    )
    fact_entities = {
        str(row["fact_id"]): str(row["entity_id"]) for row in fact_entity_rows
    }
    for row in signal_rows:
        altered_plan = json.loads(row["operator_plan"])
        altered_plan["role_fact_ids"] = {
            role: [
                fact_id
                for fact_id in fact_ids
                if fact_entities[str(fact_id)] != omitted_entity_id
            ]
            for role, fact_ids in altered_plan["role_fact_ids"].items()
        }
        db.execute(
            "UPDATE financial_signal_instances SET operator_plan = ? "
            "WHERE signal_id = ?",
            (json.dumps(altered_plan), row["signal_id"]),
        )

    malicious_entity_ids = [
        entity_id for entity_id in entities if entity_id != omitted_entity_id
    ]
    malicious_contract = dict(peer_contract)
    malicious_contract["expected_scope_entity_ids"] = malicious_entity_ids
    malicious_contract["scope_membership_hash"] = scope_membership_hash(
        malicious_contract
    )
    for table, key, value in (
        (
            "analysis_candidates",
            "candidate_id",
            peer_candidate["candidate_id"],
        ),
        (
            "analysis_evidence_bundles",
            "evidence_bundle_id",
            peer_bundle["evidence_bundle_id"],
        ),
    ):
        db.execute(
            f"UPDATE {table} SET entity_ids = ?, expected_scope_entity_ids = ?, "
            "scope_membership_hash = ?, peer_scope_contract = ? "
            f"WHERE {key} = ?",
            (
                json.dumps(malicious_entity_ids),
                json.dumps(malicious_entity_ids),
                malicious_contract["scope_membership_hash"],
                json.dumps(malicious_contract),
                value,
            ),
        )
    omitted_peer = validate_analysis_samples(db, report["analysis_build_id"])
    assert omitted_peer["failure_counts"]["peer_scope_recomputed_universe"] == 1
    assert omitted_peer["failure_counts"]["peer_scope_fact_representation"] == 1

    db.execute(
        "UPDATE analysis_candidates SET entity_ids = ?, "
        "expected_scope_entity_ids = ?, scope_membership_hash = ?, "
        "peer_scope_contract = ? WHERE candidate_id = ?",
        (
            peer_candidate["entity_ids"],
            peer_candidate["expected_scope_entity_ids"],
            peer_candidate["scope_membership_hash"],
            peer_candidate["peer_scope_contract"],
            peer_candidate["candidate_id"],
        ),
    )
    db.execute(
        "UPDATE analysis_evidence_bundles SET entity_ids = ?, "
        "expected_scope_entity_ids = ?, scope_membership_hash = ?, "
        "peer_scope_contract = ? WHERE evidence_bundle_id = ?",
        (
            peer_bundle["entity_ids"],
            peer_bundle["expected_scope_entity_ids"],
            peer_bundle["scope_membership_hash"],
            peer_bundle["peer_scope_contract"],
            peer_bundle["evidence_bundle_id"],
        ),
    )
    for signal_id, operator_plan in original_plans.items():
        db.execute(
            "UPDATE financial_signal_instances SET operator_plan = ? "
            "WHERE signal_id = ?",
            (operator_plan, signal_id),
        )
    restored_peer = validate_analysis_samples(db, report["analysis_build_id"])
    assert restored_peer["quality_status"] == "passed"

    manifest = export_analysis_jsonl(
        db,
        report["analysis_build_id"],
        str(tmp_path / "exports"),
    )
    assert manifest["sample_count"] == 6
    train_path = Path(
        tmp_path / "exports" / report["analysis_build_id"] / "sft" / "train.jsonl"
    )
    assert train_path.exists()
    benchmark_paths = [
        Path(path) for path in manifest["written_files"] if "/benchmark/" in path
    ]
    benchmark_row = json.loads(benchmark_paths[0].read_text().splitlines()[0])
    assert benchmark_row["evidence_bundle"]["signals"]
    assert benchmark_row["expected_claim_schema"]["mandatory_claim_ids"]
    assert "numeric_slots" in benchmark_row["expected_claim_schema"]

    plan_row = db.fetchone(
        "SELECT claim_graph, required_caveat_ids FROM analysis_claim_plans "
        "WHERE analysis_build_id = ? ORDER BY claim_plan_id LIMIT 1",
        (report["analysis_build_id"],),
    )
    claim_graph = json.loads(plan_row["claim_graph"])
    required_claim = next(claim for claim in claim_graph if claim["is_required"])
    assert required_claim["allowed_entity_ids"]
    assert required_claim["allowed_metric_ids"]
    assert required_claim["allowed_periods"]
    assert required_claim["allowed_predicates"]
    assert required_claim["forbidden_claim_extensions"]
    assert json.loads(plan_row["required_caveat_ids"]) == [
        "bounded_structured_evidence"
    ]

    context_sample = db.fetchone(
        "SELECT analysis_sample_id, claim_alignment, caveats FROM analysis_samples "
        "WHERE analysis_build_id = ? ORDER BY analysis_sample_id LIMIT 1",
        (report["analysis_build_id"],),
    )
    original_alignment = json.loads(context_sample["claim_alignment"])
    unknown_entity_alignment = json.loads(context_sample["claim_alignment"])
    unknown_entity_alignment[0]["context_bindings"]["entity_ids"].append(
        "UNREGISTERED_ENTITY"
    )
    unknown_entity_alignment[0]["context_bindings"]["metric_ids"].append(
        "unregistered_metric"
    )
    unknown_entity_alignment[0]["context_bindings"]["periods"].append(2099)
    unknown_entity_alignment[0]["context_bindings"]["predicates"].append(
        "unregistered_predicate"
    )
    unknown_entity_alignment[0]["context_bindings"]["numeric_slot_ids"].append(
        "unregistered_numeric_slot"
    )
    db.execute(
        "UPDATE analysis_samples SET claim_alignment = ? WHERE analysis_sample_id = ?",
        (json.dumps(unknown_entity_alignment), context_sample["analysis_sample_id"]),
    )
    unknown_entity = validate_analysis_samples(db, report["analysis_build_id"])
    assert unknown_entity["failure_counts"]["unknown_entity_count"] == 1
    assert unknown_entity["failure_counts"]["unknown_metric_count"] == 1
    assert unknown_entity["failure_counts"]["unknown_period_count"] == 1
    assert unknown_entity["failure_counts"]["unknown_predicate_count"] == 1
    assert unknown_entity["failure_counts"]["unknown_numeric_slot_count"] == 1
    db.execute(
        "UPDATE analysis_samples SET claim_alignment = ? WHERE analysis_sample_id = ?",
        (json.dumps(original_alignment), context_sample["analysis_sample_id"]),
    )

    forbidden_extension_alignment = json.loads(context_sample["claim_alignment"])
    forbidden_extension_alignment[0]["claim_extensions"] = [
        "management_quality_judgment"
    ]
    db.execute(
        "UPDATE analysis_samples SET claim_alignment = ? WHERE analysis_sample_id = ?",
        (
            json.dumps(forbidden_extension_alignment),
            context_sample["analysis_sample_id"],
        ),
    )
    forbidden_extension = validate_analysis_samples(db, report["analysis_build_id"])
    assert forbidden_extension["failure_counts"]["forbidden_claim_extension_count"] == 1
    db.execute(
        "UPDATE analysis_samples SET claim_alignment = ? WHERE analysis_sample_id = ?",
        (json.dumps(original_alignment), context_sample["analysis_sample_id"]),
    )

    original_caveats = json.loads(context_sample["caveats"])
    extra_caveats = [
        *original_caveats,
        {"caveat_id": "unknown_caveat", "sentence": "x"},
    ]
    db.execute(
        "UPDATE analysis_samples SET caveats = ? WHERE analysis_sample_id = ?",
        (json.dumps(extra_caveats), context_sample["analysis_sample_id"]),
    )
    caveat_tamper = validate_analysis_samples(db, report["analysis_build_id"])
    assert caveat_tamper["failure_counts"]["caveat_id_exact_match"] == 1
    db.execute(
        "UPDATE analysis_samples SET caveats = ? WHERE analysis_sample_id = ?",
        (json.dumps(original_caveats), context_sample["analysis_sample_id"]),
    )

    db.execute(
        "UPDATE analysis_builds SET signal_registry_manifest_hash = ? "
        "WHERE analysis_build_id = ?",
        ("tampered_manifest", report["analysis_build_id"]),
    )
    drifted = validate_analysis_samples(db, report["analysis_build_id"])
    assert drifted["quality_status"] == "failed"
    assert drifted["failure_counts"]["signal_registry_contract"] == 6
    db.execute(
        "UPDATE analysis_builds SET signal_registry_manifest_hash = ? "
        "WHERE analysis_build_id = ?",
        (
            report["manifests"]["signal_registry_manifest_hash"],
            report["analysis_build_id"],
        ),
    )

    discourse_sample = db.fetchone(
        "SELECT analysis_sample_id, instruction, generation_metadata "
        "FROM analysis_samples WHERE analysis_build_id = ? "
        "ORDER BY analysis_sample_id LIMIT 1",
        (report["analysis_build_id"],),
    )
    original_instruction = str(discourse_sample["instruction"])
    original_generation_metadata = json.loads(
        discourse_sample["generation_metadata"]
    )
    db.execute(
        "UPDATE analysis_samples SET instruction = ? WHERE analysis_sample_id = ?",
        ("Invented investment instruction", discourse_sample["analysis_sample_id"]),
    )
    instruction_tamper = validate_analysis_samples(db, report["analysis_build_id"])
    assert instruction_tamper["failure_counts"][
        "analysis_instruction_surface_contract"
    ] == 1
    db.execute(
        "UPDATE analysis_samples SET instruction = ? WHERE analysis_sample_id = ?",
        (original_instruction, discourse_sample["analysis_sample_id"]),
    )

    altered_generation_metadata = dict(original_generation_metadata)
    altered_generation_metadata["discourse_plan"] = dict(
        original_generation_metadata["discourse_plan"]
    )
    altered_generation_metadata["discourse_plan"]["transition_ids"] = list(
        altered_generation_metadata["discourse_plan"]["transition_ids"]
    )
    altered_generation_metadata["discourse_plan"]["transition_ids"][0] = (
        "invented_transition"
    )
    db.execute(
        "UPDATE analysis_samples SET generation_metadata = ? "
        "WHERE analysis_sample_id = ?",
        (
            json.dumps(altered_generation_metadata),
            discourse_sample["analysis_sample_id"],
        ),
    )
    discourse_tamper = validate_analysis_samples(db, report["analysis_build_id"])
    assert discourse_tamper["failure_counts"][
        "analysis_discourse_plan_contract"
    ] == 1
    db.execute(
        "UPDATE analysis_samples SET generation_metadata = ? "
        "WHERE analysis_sample_id = ?",
        (
            json.dumps(original_generation_metadata),
            discourse_sample["analysis_sample_id"],
        ),
    )

    sample = db.fetchone(
        "SELECT analysis_sample_id, analysis_text FROM analysis_samples "
        "WHERE analysis_build_id = ? ORDER BY analysis_sample_id LIMIT 1",
        (report["analysis_build_id"],),
    )
    db.execute(
        "UPDATE analysis_samples SET analysis_text = ? WHERE analysis_sample_id = ?",
        (
            str(sample["analysis_text"])
            + " Operating cash flow strongly supports profit growth and is not a "
            "material risk caveat.",
            sample["analysis_sample_id"],
        ),
    )
    reversed_text = validate_analysis_samples(db, report["analysis_build_id"])
    assert reversed_text["quality_status"] == "failed"
    assert reversed_text["failure_counts"]["analysis_text_render_contract"] == 1

    db.execute(
        "UPDATE analysis_samples SET analysis_text = ? WHERE analysis_sample_id = ?",
        (
            str(sample["analysis_text"])
            + " Investors should buy it at a target price of 123.",
            sample["analysis_sample_id"],
        ),
    )
    tampered = validate_analysis_samples(db, report["analysis_build_id"])
    assert tampered["quality_status"] == "failed"
    assert tampered["failure_counts"]["forbidden_claim_count"] == 1
    assert tampered["failure_counts"]["unsupported_numeric_count"] == 1
    db.close()
