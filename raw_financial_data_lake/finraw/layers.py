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
}

LAYER_DESCRIPTIONS: dict[str, str] = {
    "raw_lake": "Original source material and provenance only; no canonical financial claims are created here.",
    "fact_build": "Canonical entities, metric ontology, atomic facts, standardized facts, and document candidates built from raw records.",
    "fact_validation": "Quality checks, source-definition crosswalks, frequency metadata, fact-level graph_ready gates, conflict and comparability support.",
    "qa_ready": "Derived facts, KG artifacts, and future QA outputs that consume graph-ready standardized facts.",
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
