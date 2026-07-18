from __future__ import annotations

from typing import Any

LAYER_TABLES: dict[str, list[str]] = {
    "raw_lake": [
        "source_registry",
        "ingestion_jobs",
        "raw_objects",
        "raw_records",
        "source_entities",
        "raw_dataset_snapshots",
        "data_coverage_report",
    ],
    "fact_build": [
        "canonical_entities",
        "entity_alias_map",
        "canonical_securities",
        "entity_relationships",
        "source_series_entity_map",
        "metrics",
        "metric_alias_map",
        "atomic_facts",
        "standardized_facts",
        "source_documents",
        "document_text_chunks",
        "raw_extracted_tables",
        "candidate_facts",
    ],
    "fact_validation": [
        "source_metric_definitions",
        "time_series_frequency_map",
        "fact_quality_checks",
    ],
    "qa_ready": [
        "derived_facts",
        "kg_builds",
        "kg_nodes",
        "kg_edges",
        "kg_quality_checks",
        "kg_archives",
    ],
    "qa_build": [
        "qa_builds",
        "qa_templates",
        "qa_graph_patterns",
        "qa_pattern_mining_runs",
        "qa_pattern_proposals",
        "qa_candidates",
        "qa_operation_plans",
        "qa_samples",
        "qa_evidence_paths",
        "qa_quality_checks",
        "qa_archives",
    ],
    "analysis_build": [
        "analysis_builds",
        "financial_signal_specs",
        "financial_signal_instances",
        "analysis_patterns",
        "analysis_pattern_proposals",
        "analysis_pattern_catalog_releases",
        "analysis_pattern_catalog_entries",
        "analysis_candidates",
        "analysis_evidence_bundles",
        "analysis_claim_plans",
        "analysis_samples",
        "analysis_quality_checks",
    ],
}

LAYER_COMMANDS: dict[str, list[str]] = {
    "raw_lake": [
        "init-db",
        "seed-sources",
        "ingest",
        "validate",
        "quality-report",
        "coverage-report",
        "refresh-coverage-report",
    ],
    "fact_build": [
        "refresh-entities",
        "refresh-metrics",
        "refresh-atomic-facts",
        "standardize-facts",
        "refresh-document-extraction",
    ],
    "fact_validation": [
        "refresh-source-definitions",
        "refresh-frequency-map",
        "standardize-facts",
        "enforce-quality",
        "enforce-fact-quality",
    ],
    "qa_ready": [
        "refresh-derived-facts",
        "build-kg",
        "kg-quality-report",
        "export-kg-jsonl",
        "kg-retention",
    ],
    "qa_build": [
        "mine-qa-patterns",
        "build-qa-candidates",
        "generate-qa",
        "validate-qa",
        "split-qa",
        "build-qa",
        "export-qa-jsonl",
        "qa-analysis",
        "qa-retention",
        "artifact-retention",
    ],
    "analysis_build": [
        "build-analysis",
        "validate-analysis",
        "analysis-diversity",
        "export-analysis-jsonl",
    ],
}

LAYER_OUTPUTS: dict[str, dict[str, str]] = {
    "raw_lake": {
        "objects": "data/fin_raw/",
        "audit": "data/audit/raw_lake/",
        "exports": "data/layered_exports/raw_lake/",
    },
    "fact_build": {
        "audit": "data/audit/fact_build/",
        "exports": "data/layered_exports/fact_build/",
    },
    "fact_validation": {
        "audit": "data/audit/fact_validation/",
        "exports": "data/layered_exports/fact_validation/",
    },
    "qa_ready": {
        "audit": "data/audit/qa_ready/",
        "exports": "data/layered_exports/qa_ready/",
    },
    "qa_build": {
        "audit": "data/audit/qa_build/",
        "exports": "data/qa_exports/",
    },
    "analysis_build": {
        "audit": "data/audit/analysis_build/",
        "exports": "data/analysis_exports/",
    },
}

LAYER_DESCRIPTIONS: dict[str, str] = {
    "raw_lake": "Original source material and provenance only; no canonical financial claims are created here.",
    "fact_build": "Canonical entities, metric ontology, atomic facts, standardized facts, and document candidates built from raw records.",
    "fact_validation": "Quality checks, source-definition crosswalks, frequency metadata, fact-level graph_ready gates, conflict and comparability support.",
    "qa_ready": "Derived facts and versioned KG artifacts that consume graph-ready standardized facts.",
    "qa_build": "Graph-pattern and legacy QA candidates, executable operation plans, samples, evidence subgraphs, rubrics, quality checks, splits, and benchmark exports pinned to a KG build.",
    "analysis_build": "Semi-open, claim-grounded financial analysis built from pinned facts, reproducible signals, evidence bundles, claim plans, valid conclusion sets, and independent verification.",
}


def layer_manifest() -> dict[str, Any]:
    return {
        layer: {
            "description": LAYER_DESCRIPTIONS[layer],
            "tables": LAYER_TABLES[layer],
            "commands": LAYER_COMMANDS[layer],
            "outputs": LAYER_OUTPUTS[layer],
        }
        for layer in LAYER_TABLES
    }


def tables_for_layer(layer: str) -> list[str]:
    try:
        return LAYER_TABLES[layer]
    except KeyError as exc:
        known = ", ".join(sorted(LAYER_TABLES))
        raise ValueError(f"Unknown layer {layer!r}; expected one of: {known}") from exc
