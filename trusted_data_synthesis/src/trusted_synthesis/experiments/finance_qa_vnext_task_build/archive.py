"""Verified KG archive adapter for the existing indexed QA Build interface.

This is a read projection of an actual successful historical graph, not a new
fact extraction or an assertion that omitted upstream columns were recovered.
Raw graph rows remain unchanged. Reconstructed serving fields are explicitly
recorded and can only follow existing graph membership and edges.
"""

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import pyarrow.parquet as pq
from finraw.builds import ensure_build_schema
from finraw.db.client import MetadataDB
from finraw.kg_builder import ensure_kg_schema


class RecordDB(MetadataDB):
    """The new adapter consumes mappings, irrespective of SQLite Row objects."""

    def fetchall(self, sql, params=()):
        return [dict(row) for row in super().fetchall(sql, params)]

    def fetchone(self, sql, params=()):
        row = super().fetchone(sql, params)
        return None if row is None else dict(row)


ARCHIVE = "raw_financial_data_lake/data/kg_archive/kg_build_id=kg_20260723_191638_396e6b92"
OUTPUT = "trusted_data_synthesis/artifacts/qa_vnext_task_build/task_factory_20260911"
WORK = "trusted_data_synthesis/artifacts/qa_vnext_task_build/runtime_20260911"
PROJECTIONS = {
    "Fact": ("standardized_facts", "fact_id"),
    "DerivedFact": ("derived_facts", "derived_id"),
    "Entity": ("canonical_entities", "entity_id"),
    "Metric": ("metrics", "metric_id"),
    "SourceDefinition": ("source_metric_definitions", "definition_id"),
    "SourceDocument": ("source_documents", "document_id"),
    "RawObject": ("raw_objects", "raw_object_id"),
}


def require(condition, code):
    if not condition:
        raise ValueError(code)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def record(kind, **fields):
    body = {"schema_version": "finance_qa_vnext_task_build.v1." + kind, **fields}
    raw = json.dumps(
        body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    return {**body, "id": kind + ":" + hashlib.sha256(raw).hexdigest()}


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(
            value,
            stream,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )


def validate_record(value, kind):
    body = {key: item for key, item in value.items() if key not in {"id", "schema_version"}}
    require(value == record(kind, **body), "record.content_addressed_identity")
    return value


def validate_archive(root):
    directory = Path(root) / ARCHIVE
    value = json.loads((directory / "manifest.json").read_bytes())
    kg = value["build"]
    require(
        kg["status"] == "success" and kg["quality_status"] == "passed",
        "archive.successful_quality_gated_build",
    )
    require(
        kg["kg_build_id"] == value["kg_build_id"] == "kg_20260723_191638_396e6b92",
        "archive.fixed_KG_identity",
    )
    refs = []
    for table in ("kg_nodes", "kg_edges", "kg_quality_checks"):
        ref = value["files"][table]
        path = directory / (table + ".parquet")
        require(not path.is_symlink() and path.is_file(), "archive.original_regular_file")
        require(
            sha(path) == ref["sha256"] and path.stat().st_size == ref["size_bytes"],
            "archive.original_byte_identity",
        )
        require(
            pq.ParquetFile(path).metadata.num_rows == ref["row_count"], "archive.original_row_count"
        )
        refs.append(
            {
                **ref,
                "resolved_local_path": str(path.relative_to(root)),
                "original_storage_path_rewritten_in_parent": False,
            }
        )
    return value, refs


def insert(db, table, rows):
    if not rows:
        return
    rows = [dict(row) for row in rows]
    columns = [row["name"] for row in db.fetchall("PRAGMA table_info(" + table + ")")]
    used = [column for column in columns if any(column in row for row in rows)]
    require(bool(used), "archive.projection_known_schema")

    def scalar(value):
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        return value

    db.conn.executemany(
        "INSERT INTO "
        + table
        + " ("
        + ",".join(used)
        + ") VALUES ("
        + ",".join("?" for _ in used)
        + ")",
        [[scalar(row.get(column)) for column in used] for row in rows],
    )


def fact_projection(node, kg):
    require(
        node["node_type"] == "Fact" and node["source_table"] == "standardized_facts",
        "archive.original_fact_node",
    )
    value = json.loads(node["properties_json"])
    require(value["fact_id"] == node["source_pk"], "archive.fact_source_pk")
    require(value["build_id"] == kg["input_fact_build_id"], "archive.fact_parent_build")
    require(
        node["kg_build_id"] == kg["kg_build_id"] and node["is_active"] == 1,
        "archive.valid_materialized_fact",
    )
    require(value.get("graph_ready_reason") == "ready", "archive.explicit_graph_readiness_reason")
    require(
        value["verification_status"] in {"single_source", "cross_verified"}
        and not value.get("is_forecast"),
        "archive.verified_nonforecast_fact",
    )
    # This flag is proven by membership in the verified graph and ready reason.
    # It is not supplied by a keyword screen or inferred from numeric equality.
    return {**value, "graph_ready": 1, "is_active": 1}


def restore(root):
    root = Path(root).resolve()
    archived, refs = validate_archive(root)
    kg = archived["build"]
    directory = root / OUTPUT / "archive_input"
    require(not directory.exists(), "archive.new_stage_only")
    directory.mkdir(parents=True)
    write_json(directory / "original_manifest.json", archived)
    write_json(directory / "source_references.json", refs)
    working = root / WORK
    working.mkdir(parents=True, exist_ok=True)
    database = working / "qa_build.sqlite3"
    require(not database.exists(), "archive.new_isolated_database_only")
    db = MetadataDB(str(database))
    db.init_schema()
    ensure_build_schema(db)
    ensure_kg_schema(db)
    counts = Counter()
    projections = defaultdict(list)
    node_by_id = {}
    with db.transaction():
        insert(db, "kg_builds", [kg])
        for batch in pq.ParquetFile(root / ARCHIVE / "kg_nodes.parquet").iter_batches(
            batch_size=8192
        ):
            rows = batch.to_pylist()
            insert(db, "kg_nodes", rows)
            for row in rows:
                counts[row["node_type"]] += 1
                node_by_id[row["node_id"]] = (row["node_type"], row["source_pk"])
                if row["node_type"] in PROJECTIONS:
                    table, key = PROJECTIONS[row["node_type"]]
                    value = (
                        fact_projection(row, kg)
                        if row["node_type"] == "Fact"
                        else json.loads(row["properties_json"])
                    )
                    require(value.get(key) == row["source_pk"], "archive.original_source_identity")
                    projections[table].append(value)
        print(json.dumps({"restored_original_nodes": sum(counts.values())}), flush=True)
        derived_inputs = defaultdict(list)
        for batch in pq.ParquetFile(root / ARCHIVE / "kg_edges.parquet").iter_batches(
            batch_size=16384
        ):
            rows = batch.to_pylist()
            insert(db, "kg_edges", rows)
            for row in rows:
                require(row["kg_build_id"] == kg["kg_build_id"], "archive.edge_KG_identity")
                if row["relation_type"] == "DERIVED_FROM":
                    source = node_by_id[row["src_node_id"]]
                    target = node_by_id[row["dst_node_id"]]
                    require(
                        source[0] == "DerivedFact" and target[0] == "Fact",
                        "archive.derived_leaf_edge_types",
                    )
                    derived_inputs[source[1]].append(target[1])
        print(
            json.dumps({"restored_original_edges": archived["files"]["kg_edges"]["row_count"]}),
            flush=True,
        )
        for value in projections["derived_facts"]:
            require(
                value["build_id"] == kg["input_qa_build_id"]
                and value["input_build_id"] == kg["input_fact_build_id"],
                "archive.derived_parent_chain",
            )
            inputs = sorted(set(derived_inputs[value["derived_id"]]))
            require(bool(inputs), "archive.derived_actual_leaf_facts")
            if value.get("input_fact_ids"):
                existing = value["input_fact_ids"]
                require(
                    sorted(existing if isinstance(existing, list) else json.loads(existing))
                    == inputs,
                    "archive.original_derived_inputs_agree",
                )
            value["input_fact_ids"] = inputs
            value["is_active"] = 1
        omitted_columns = {}
        for table, rows in projections.items():
            columns = {row["name"] for row in db.fetchall("PRAGMA table_info(" + table + ")")}
            omitted_columns[table] = sorted(set().union(*(set(row) for row in rows)) - columns)
            insert(db, table, rows)
        insert(
            db,
            "kg_quality_checks",
            pq.ParquetFile(root / ARCHIVE / "kg_quality_checks.parquet").read().to_pylist(),
        )
    report = record(
        "pinned_archive_serving_projection",
        status="ARCHIVE_INPUT_RESTORED_FOR_QA_BUILD",
        kg_build=kg,
        source_references=refs,
        node_type_counts=dict(counts),
        source_table_projection_counts={table: len(rows) for table, rows in projections.items()},
        source_columns_not_in_current_serving_schema=omitted_columns,
        database_path=str(database.relative_to(root)),
        copied_existing_build_id_not_new_fact_build=True,
        archived_parent_rows_unchanged=True,
        projection_contract={
            "Fact.graph_ready": (
                "existing valid Fact node plus graph_ready_reason=ready and passed archived KG"
            ),
            "DerivedFact.input_fact_ids": (
                "complete archived DERIVED_FROM edges, never operand guessing"
            ),
            "is_active": "local materialization validity; historical KG build remains inactive",
            "unavailable_original_upstream_columns": (
                "remain unavailable; not reconstructed through QA answers"
            ),
            "historical_serving_paths": (
                "mapped locally by verified bytes; not changed in original parent records"
            ),
        },
        original_PostgreSQL_mutated=False,
        original_archives_mutated=False,
        upstream_build_status_from_current_database_available=False,
        current_database_diagnostic=(
            "configured localhost:5432 refused connection; Docker access unavailable"
        ),
        authority_scope=(
            "archived successful KG snapshot, not claim of current production availability"
        ),
        new_Teacher_sessions=0,
        new_Student_runs=0,
        newly_generated_tasks=0,
    )
    write_json(directory / "report.json", report)
    db.close()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    print(json.dumps(restore(args.root), ensure_ascii=False))


if __name__ == "__main__":
    main()
