from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from trusted_synthesis.core.evidence import EpistemicStatus, ScalarObservation
from trusted_synthesis.core.evidence.schema import SourceAuthority
from trusted_synthesis.domains.finance.adapter import FinanceArchiveAdapter
from trusted_synthesis.domains.finance.schema import FinanceArchiveConfig


def test_finance_adapter_reads_only_quality_passed_graph_facts(tmp_path: Path) -> None:
    config = _archive_fixture(tmp_path)
    adapter = FinanceArchiveAdapter(config)
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))

    inspection = adapter.inspect()
    evidence = list(adapter.iter_evidence(limit=1))
    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))

    assert inspection["compatible"] is True
    assert inspection["read_only"] is True
    assert inspection["fact_node_count"] == 1
    assert len(evidence) == 1
    assert evidence[0].subject.name == "Example Company"
    assert evidence[0].predicate == "revenue"
    assert isinstance(evidence[0].payload, ScalarObservation)
    assert evidence[0].source.authority == SourceAuthority.OFFICIAL
    assert evidence[0].epistemic_status == EpistemicStatus.OBSERVED
    assert evidence[0].provenance.build_ids["kg"] == "kg_test"
    assert before == after


def _archive_fixture(root: Path) -> FinanceArchiveConfig:
    catalog_root = root / "catalog"
    catalog_root.mkdir()
    _parquet(
        catalog_root / "canonical_entities.parquet",
        [
            {
                "entity_id": "EXAMPLE_US",
                "canonical_name": "Example Company",
                "entity_type": "company",
                "market": "US",
                "country": "US",
            }
        ],
    )
    _parquet(
        catalog_root / "metrics.parquet",
        [
            {
                "metric_id": "revenue",
                "canonical_name": "Revenue",
                "metric_category": "financial_statement",
                "period_type": "period_flow",
            }
        ],
    )
    _parquet(
        catalog_root / "source_registry.parquet",
        [
            {
                "source_id": "sec_companyfacts",
                "source_name": "SEC Company Facts",
                "authority_level": "S1_official",
                "provider": "SEC",
                "base_url": "https://data.sec.gov/",
                "license_note": None,
            }
        ],
    )
    _parquet(
        catalog_root / "source_metric_definitions.parquet",
        [{"definition_id": "sdef_revenue", "definition_text": "GAAP revenue"}],
    )
    report_path = root / "kg_build_report.json"
    report_path.write_text(
        json.dumps(
            {
                "kg_build_id": "kg_test",
                "quality": {
                    "kg_quality_gate_status": "passed",
                    "graph_schema_version": "3.0",
                    "input_fact_build_id": "fact_build_test",
                    "fact_node_count": 1,
                    "derived_fact_node_count": 0,
                    "node_count": 5,
                    "edge_count": 4,
                },
            }
        ),
        encoding="utf-8",
    )
    nodes_path = root / "kg_nodes.jsonl"
    nodes_path.write_text(
        json.dumps(
            {
                "is_active": 1,
                "kg_build_id": "kg_test",
                "node_type": "Fact",
                "properties": {
                    "stable_fact_id": "fact_revenue_2023",
                    "fact_id": "fact_revenue_2023__build",
                    "build_id": "standardized_build_test",
                    "entity_id": "EXAMPLE_US",
                    "metric_id": "revenue",
                    "normalized_value": "123.45",
                    "normalized_unit": "million USD",
                    "normalized_currency": "USD",
                    "period_start": "2023-01-01",
                    "period_end": "2023-12-31",
                    "fiscal_year": 2023,
                    "fiscal_quarter": "FY",
                    "time_basis": "fiscal_period",
                    "frequency": "annual",
                    "metric_period_type": "period_flow",
                    "financial_scope_type": "consolidated_company",
                    "entity_scope_id": "EXAMPLE_US",
                    "source_id": "sec_companyfacts",
                    "source_definition_id": "sdef_revenue",
                    "raw_object_id": "raw_example",
                    "verification_status": "single_source",
                    "graph_ready_reason": "ready",
                    "is_forecast": 0,
                    "confidence_score": 0.99,
                    "comparability_level": "xbrl_concept_level",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    edges_path = root / "kg_edges.jsonl"
    edges_path.write_text("", encoding="utf-8")
    return FinanceArchiveConfig(
        adapter_version="finance_archive.v1",
        archive_root=root,
        kg_nodes_path=nodes_path,
        kg_edges_path=edges_path,
        kg_report_path=report_path,
        catalog_root=catalog_root,
        exclude_forecasts=True,
        accepted_verification_statuses=("single_source", "cross_verified"),
        required_kg_build_id="kg_test",
        required_graph_schema_version="3.0",
    )


def _parquet(path: Path, rows: list[dict[str, object]]) -> None:
    pq.write_table(pa.Table.from_pylist(rows), path)
