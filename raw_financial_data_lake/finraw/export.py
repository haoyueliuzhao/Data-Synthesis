from __future__ import annotations

import json
from pathlib import Path

from finraw.db.client import MetadataDB
from finraw.layers import LAYER_TABLES


EXPORT_TABLES = [
    "source_registry",
    "ingestion_jobs",
    "raw_objects",
    "raw_records",
    "source_entities",
    "raw_dataset_snapshots",
    "data_coverage_report",
    "canonical_entities",
    "entity_alias_map",
    "source_series_entity_map",
    "entity_relationships",
    "canonical_securities",
    "metrics",
    "metric_alias_map",
    "atomic_facts",
    "standardized_facts",
    "fact_quality_checks",
    "derived_facts",
    "source_metric_definitions",
    "time_series_frequency_map",
    "source_documents",
    "document_text_chunks",
    "raw_extracted_tables",
    "candidate_facts",
    "kg_builds",
    "kg_nodes",
    "kg_edges",
    "kg_quality_checks",
    "kg_archives",
]


def _normalise_parquet_value(value):
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return value


def export_jsonl(db: MetadataDB, output_dir: str, tables: list[str] | None = None) -> list[Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for table in tables or EXPORT_TABLES:
        rows = db.fetchall(f"SELECT * FROM {table}")
        path = out / f"{table}.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True, default=str) + "\n")
        paths.append(path)
    return paths


def export_parquet(db: MetadataDB, output_dir: str, tables: list[str] | None = None) -> list[Path]:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RuntimeError("Parquet export requires pyarrow. Install pyarrow or use export-jsonl.") from exc

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for table in tables or EXPORT_TABLES:
        rows = [
            {key: _normalise_parquet_value(value) for key, value in dict(row).items()}
            for row in db.fetchall(f"SELECT * FROM {table}")
        ]
        path = out / f"{table}.parquet"
        pq.write_table(pa.Table.from_pylist(rows or [{}]), path)
        paths.append(path)
    return paths


def export_layer_jsonl(db: MetadataDB, layer: str, output_dir: str) -> list[Path]:
    return export_jsonl(db, output_dir, tables=LAYER_TABLES[layer])


def export_layer_parquet(db: MetadataDB, layer: str, output_dir: str) -> list[Path]:
    return export_parquet(db, output_dir, tables=LAYER_TABLES[layer])
