from __future__ import annotations

import argparse
import json

from finraw.atomic_facts import refresh_atomic_facts
from finraw.builds import mark_running_builds_failed
from finraw.cninfo_discovery import discover_cninfo_announcements, discover_cninfo_from_strategy, write_cninfo_config
from finraw.config import load_config
from finraw.connectors.cninfo import CninfoConnector
from finraw.connectors.fred import FredConnector
from finraw.connectors.imf import ImfSdmxConnector
from finraw.connectors.sec import SecBulkConnector
from finraw.connectors.sec_filings import SecFilingsConnector
from finraw.connectors.sec_sample import SecCompanyJsonConnector
from finraw.connectors.worldbank import WorldBankConnector
from finraw.coverage import build_data_coverage_report, refresh_data_coverage_report, write_coverage_outputs
from finraw.derived_facts import refresh_derived_facts
from finraw.document_extraction import refresh_document_extraction
from finraw.db.client import create_metadata_db
from finraw.entity_normalization import refresh_entity_normalization
from finraw.export import export_jsonl, export_layer_jsonl, export_layer_parquet, export_parquet
from finraw.layers import LAYER_TABLES, layer_manifest
from finraw.fact_quality import enforce_fact_quality_gates
from finraw.fact_standardization import refresh_fact_standardization
from finraw.kg_builder import build_kg, export_kg_jsonl, kg_quality_report
from finraw.kg_retention import enforce_kg_retention
from finraw.kg_query import query_derived_facts, query_facts, query_neighbors
from finraw.metric_ontology import refresh_metric_ontology
from finraw.qa.export import export_qa_jsonl
from finraw.qa.diversity import build_qa_diversity_report
from finraw.qa.pipeline import build_qa, build_qa_candidates, generate_qa_samples, split_qa_samples, validate_qa_samples
from finraw.source_definitions import refresh_source_metric_definitions, refresh_time_series_frequency_map
from finraw.quality import QualityGateError, enforce_quality_gates
from finraw.storage import RawObjectStore
from finraw.validation import quality_report, validate_raw_objects


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a Raw Financial Data Lake.")
    parser.add_argument("--config", help="Path to config JSON.", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("layers", help="Print logical data layers, tables, commands, and output directories as JSON.")
    sub.add_parser("init-db", help="Create metadata database schema.")
    sub.add_parser("seed-sources", help="Insert source registry seed rows.")

    ingest = sub.add_parser("ingest", help="Run an ingestion connector.")
    ingest.add_argument("source", choices=["sec-sample", "sec-filings", "sec-bulk", "fred", "worldbank", "imf", "cninfo", "test", "all"])
    ingest.add_argument("--dry-run", action="store_true", help="Print targets without downloading or writing data.")

    export_jsonl_parser = sub.add_parser("export-jsonl", help="Export metadata tables to JSONL.")
    export_jsonl_parser.add_argument("output_dir")

    export_parquet_parser = sub.add_parser("export-parquet", help="Export metadata tables to Parquet if pyarrow is installed.")
    export_parquet_parser.add_argument("output_dir")

    export_layer_jsonl_parser = sub.add_parser("export-layer-jsonl", help="Export one logical layer to JSONL.")
    export_layer_jsonl_parser.add_argument("layer", choices=sorted(LAYER_TABLES))
    export_layer_jsonl_parser.add_argument("output_dir")

    export_layer_parquet_parser = sub.add_parser("export-layer-parquet", help="Export one logical layer to Parquet if pyarrow is installed.")
    export_layer_parquet_parser.add_argument("layer", choices=sorted(LAYER_TABLES))
    export_layer_parquet_parser.add_argument("output_dir")

    discover_cninfo = sub.add_parser("discover-cninfo", help="Discover CNInfo announcement PDF URLs and write a config fragment.")
    discover_cninfo.add_argument("--stock", required=True, help="CNInfo stock selector, e.g. 000001 or 000001,gssz0000001")
    discover_cninfo.add_argument("--start-date", required=True, help="Start date YYYY-MM-DD")
    discover_cninfo.add_argument("--end-date", required=True, help="End date YYYY-MM-DD")
    discover_cninfo.add_argument("--category", default="annual", help="annual, semiannual, q1, q3, or raw CNInfo category code")
    discover_cninfo.add_argument("--max-pages", type=int, default=1)
    discover_cninfo.add_argument("--page-size", type=int, default=30)
    discover_cninfo.add_argument("--output", default="config/cninfo_announcements.generated.json")

    discover_batch = sub.add_parser("discover-cninfo-batch", help="Discover CNInfo announcement PDF URLs from a stock-pool strategy config.")
    discover_batch.add_argument("--strategy", required=True)
    discover_batch.add_argument("--output", default="config/cninfo_announcements.generated.json")

    sub.add_parser("quality-report", help="Print data quality and coverage summary as JSON.")

    coverage_report = sub.add_parser("coverage-report", help="Print detailed source/entity/time/data-type coverage as JSON.")
    coverage_report.add_argument("--output-dir", help="Optional directory for JSON and Markdown coverage reports.")

    refresh_coverage = sub.add_parser("refresh-coverage-report", help="Refresh data_coverage_report table and optionally write report files.")
    refresh_coverage.add_argument("--output-dir", default="data/audit", help="Directory for JSON and Markdown coverage reports.")
    refresh_entities = sub.add_parser("refresh-entities", help="Rebuild canonical_entities and entity_alias_map from raw/source metadata.")
    refresh_entities.add_argument("--output-dir", default="data/audit", help="Directory for entity normalization report files.")

    refresh_metrics = sub.add_parser("refresh-metrics", help="Rebuild metrics and metric_alias_map ontology tables from raw/source metadata.")
    refresh_metrics.add_argument("--output-dir", default="data/audit", help="Directory for metric ontology report files.")

    refresh_facts = sub.add_parser("refresh-atomic-facts", help="Extract atomic_facts from structured raw records.")
    refresh_facts.add_argument("--output-dir", default="data/audit", help="Directory for atomic facts extraction report files.")
    refresh_facts.add_argument("--batch-size", type=int, default=5000, help="Batch size for atomic_facts inserts.")

    standardize_facts = sub.add_parser("standardize-facts", help="Normalize units/time fields and validate atomic facts.")
    standardize_facts.add_argument("--output-dir", default="data/audit", help="Directory for fact standardization report files.")
    standardize_facts.add_argument("--batch-size", type=int, default=10000, help="Batch size for standardized_facts inserts.")

    derived_facts = sub.add_parser("refresh-derived-facts", help="Build derived_facts from standardized_facts.")
    derived_facts.add_argument("--output-dir", default="data/audit", help="Directory for derived facts report files.")
    derived_facts.add_argument("--batch-size", type=int, default=5000, help="Batch size for derived_facts inserts.")

    source_defs = sub.add_parser("refresh-source-definitions", help="Build source_metric_definitions crosswalk metadata.")
    source_defs.add_argument("--output-dir", default="data/audit", help="Directory for source definition report files.")

    frequency_map = sub.add_parser("refresh-frequency-map", help="Build time_series_frequency_map for FRED and other series sources.")
    frequency_map.add_argument("--output-dir", default="data/audit", help="Directory for frequency map report files.")

    doc_extract = sub.add_parser("refresh-document-extraction", help="Build document text chunks, table placeholders, and candidate document facts.")
    doc_extract.add_argument("--output-dir", default="data/audit", help="Directory for document extraction report files.")

    sub.add_parser("enforce-quality", help="Enforce configured raw object quality gates and storage budget.")

    enforce_fact_quality = sub.add_parser("enforce-fact-quality", help="Enforce fact-level quality gates and mark graph-ready standardized facts.")
    enforce_fact_quality.add_argument("--output-dir", default="data/audit/fact_validation", help="Directory for fact quality report files.")

    build_kg_parser = sub.add_parser("build-kg", help="Build a versioned property graph from graph-ready facts and derived facts.")
    build_kg_parser.add_argument("--output-dir", default="data/audit/kg", help="Directory for KG build and quality reports.")
    build_kg_parser.add_argument("--batch-size", type=int, default=20000, help="Batch size for kg_nodes and kg_edges inserts.")

    kg_quality = sub.add_parser("kg-quality-report", help="Write and print KG quality checks for the active or selected KG build.")
    kg_quality.add_argument("--kg-build-id", help="Optional KG build ID. Defaults to the active KG build.")
    kg_quality.add_argument("--output-dir", default="data/audit/kg", help="Directory for KG quality report files.")

    kg_export = sub.add_parser("export-kg-jsonl", help="Export active or selected KG nodes and edges to JSONL.")
    kg_export.add_argument("output_dir")
    kg_export.add_argument("--kg-build-id", help="Optional KG build ID. Defaults to the active KG build.")

    kg_retention = sub.add_parser("kg-retention", help="Plan or execute hot/cold KG build retention.")
    kg_retention.add_argument("--hot-builds", type=int, help="Number of successful KG builds to keep in PostgreSQL.")
    kg_retention.add_argument("--archive-dir", help="Cold archive directory. Defaults to config kg.retention.archive_dir.")
    kg_retention.add_argument("--output-dir", default="data/audit/kg_retention")
    kg_retention.add_argument("--execute", action="store_true", help="Write verified Parquet/ZSTD archives.")
    kg_retention.add_argument("--purge", action="store_true", help="Delete archived node/edge rows after verification.")
    kg_retention.add_argument("--vacuum", action="store_true", help="VACUUM graph tables after purge.")
    kg_retention.add_argument("--batch-size", type=int, default=100000)

    kg_query = sub.add_parser("query-kg", help="Query the indexed PostgreSQL KG/fact serving layer.")
    kg_query.add_argument("mode", choices=["neighbors", "facts", "derived"])
    kg_query.add_argument("--kg-build-id")
    kg_query.add_argument("--node-id", help="Stable or versioned node ID for neighbors mode.")
    kg_query.add_argument("--direction", choices=["in", "out", "both"], default="both")
    kg_query.add_argument("--relation-type")
    kg_query.add_argument("--entity-id")
    kg_query.add_argument("--metric-id")
    kg_query.add_argument("--derived-type")
    kg_query.add_argument("--source-id")
    kg_query.add_argument("--date-from")
    kg_query.add_argument("--date-to")
    kg_query.add_argument("--limit", type=int, default=100)

    qa_candidates = sub.add_parser("build-qa-candidates", help="Build versioned structured QA candidates from a pinned KG build.")
    qa_candidates.add_argument("--kg-build-id", help="Optional KG build ID. Defaults to active KG.")
    qa_candidates.add_argument("--output-dir", default="data/audit/qa_build")
    qa_candidates.add_argument("--batch-size", type=int, default=2000)

    qa_generate = sub.add_parser("generate-qa", help="Render deterministic canonical QA samples from candidates.")
    qa_generate.add_argument("--qa-build-id", required=True)
    qa_generate.add_argument("--output-dir", default="data/audit/qa_build")
    qa_generate.add_argument("--batch-size", type=int, default=2000)

    qa_validate = sub.add_parser("validate-qa", help="Independently recompute and quality-check QA samples.")
    qa_validate.add_argument("--qa-build-id", required=True)
    qa_validate.add_argument("--output-dir", default="data/audit/qa_build")
    qa_validate.add_argument("--batch-size", type=int, default=2000)

    qa_split = sub.add_parser("split-qa", help="Assign passed semantic QA groups to leakage-safe splits.")
    qa_split.add_argument("--qa-build-id", required=True)
    qa_split.add_argument("--output-dir", default="data/audit/qa_build")

    qa_export = sub.add_parser("export-qa-jsonl", help="Export passed QA as benchmark, SFT, and trace-seed JSONL.")
    qa_export.add_argument("--qa-build-id", required=True)
    qa_export.add_argument("--output-dir", default="data/qa_exports")

    qa_analysis = sub.add_parser("qa-analysis", help="Report QA semantic diversity and KG utilization for a QA build.")
    qa_analysis.add_argument("--qa-build-id", required=True)
    qa_analysis.add_argument("--output-dir", default="data/audit/qa_analysis")

    qa_all = sub.add_parser("build-qa", help="Run candidate, generation, validation, and split stages end to end.")
    qa_all.add_argument("--kg-build-id", help="Optional KG build ID. Defaults to active KG.")
    qa_all.add_argument("--output-dir", default="data/audit/qa_build")
    qa_all.add_argument("--batch-size", type=int, default=2000)

    sub.add_parser("validate", help="Recompute checksums for saved raw objects.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = load_config(args.config)
    db = create_metadata_db(config)
    store = RawObjectStore(config["storage_root"])

    try:
        if args.command == "layers":
            print(json.dumps(layer_manifest(), ensure_ascii=False, indent=2, sort_keys=True))
        elif args.command == "init-db":
            db.init_schema()
            print(f"Initialized metadata DB: {config['metadata_db']}")
        elif args.command == "seed-sources":
            db.init_schema()
            db.seed_sources()
            print("Seeded source_registry.")
        elif args.command == "ingest":
            db.init_schema()
            db.seed_sources()
            connectors = []
            if args.source in {"sec-sample", "test", "all"}:
                connectors.append(SecCompanyJsonConnector(db, store, config, dry_run=args.dry_run))
            if args.source in {"sec-filings", "test", "all"}:
                connectors.append(SecFilingsConnector(db, store, config, dry_run=args.dry_run))
            if args.source in {"sec-bulk", "all"}:
                connectors.append(SecBulkConnector(db, store, config, dry_run=args.dry_run))
            if args.source in {"fred", "test", "all"}:
                connectors.append(FredConnector(db, store, config, dry_run=args.dry_run))
            if args.source in {"worldbank", "test", "all"}:
                connectors.append(WorldBankConnector(db, store, config, dry_run=args.dry_run))
            if args.source in {"imf", "all"}:
                connectors.append(ImfSdmxConnector(db, store, config, dry_run=args.dry_run))
            if args.source in {"cninfo", "all"}:
                connectors.append(CninfoConnector(db, store, config, dry_run=args.dry_run))
            for connector in connectors:
                connector.run()
            print("Ingestion completed.")
        elif args.command == "export-jsonl":
            paths = export_jsonl(db, args.output_dir)
            print(json.dumps([str(path) for path in paths], ensure_ascii=False, indent=2))
        elif args.command == "export-parquet":
            try:
                paths = export_parquet(db, args.output_dir)
            except RuntimeError as exc:
                print(str(exc))
            else:
                print(json.dumps([str(path) for path in paths], ensure_ascii=False, indent=2))
        elif args.command == "export-layer-jsonl":
            paths = export_layer_jsonl(db, args.layer, args.output_dir)
            print(json.dumps([str(path) for path in paths], ensure_ascii=False, indent=2))
        elif args.command == "export-layer-parquet":
            try:
                paths = export_layer_parquet(db, args.layer, args.output_dir)
            except RuntimeError as exc:
                print(str(exc))
            else:
                print(json.dumps([str(path) for path in paths], ensure_ascii=False, indent=2))
        elif args.command == "discover-cninfo":
            announcements = discover_cninfo_announcements(
                stock=args.stock,
                start_date=args.start_date,
                end_date=args.end_date,
                category=args.category,
                page_size=args.page_size,
                max_pages=args.max_pages,
            )
            path = write_cninfo_config(args.output, announcements)
            print(json.dumps({"output": str(path), "announcement_count": len(announcements)}, ensure_ascii=False, indent=2))
        elif args.command == "discover-cninfo-batch":
            with open(args.strategy, "r", encoding="utf-8") as f:
                strategy = json.load(f)
            announcements = discover_cninfo_from_strategy(strategy)
            path = write_cninfo_config(args.output, announcements)
            print(json.dumps({"output": str(path), "announcement_count": len(announcements)}, ensure_ascii=False, indent=2))
        elif args.command == "quality-report":
            print(json.dumps(quality_report(db), ensure_ascii=False, indent=2, sort_keys=True, default=str))
        elif args.command == "coverage-report":
            report = build_data_coverage_report(db, config)
            if args.output_dir:
                paths = write_coverage_outputs(report, args.output_dir)
                report["written_files"] = [str(path) for path in paths]
            print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str))
        elif args.command == "refresh-coverage-report":
            report = refresh_data_coverage_report(db, config, output_dir=args.output_dir)
            print(json.dumps({"status": "refreshed", "row_count": len(report["data_coverage_report"]), "output_dir": args.output_dir}, ensure_ascii=False, indent=2))
        elif args.command == "refresh-entities":
            report = refresh_entity_normalization(db, config, output_dir=args.output_dir)
            print(json.dumps({"status": "refreshed", "build_id": report.get("build_id"), "canonical_entity_count": report["canonical_entity_count"], "alias_count": report["alias_count"], "output_dir": args.output_dir}, ensure_ascii=False, indent=2))
        elif args.command == "refresh-metrics":
            report = refresh_metric_ontology(db, config, output_dir=args.output_dir)
            print(json.dumps({"status": "refreshed", "build_id": report.get("build_id"), "metric_count": report["metric_count"], "alias_count": report["alias_count"], "output_dir": args.output_dir}, ensure_ascii=False, indent=2))
        elif args.command == "refresh-atomic-facts":
            report = refresh_atomic_facts(db, config, output_dir=args.output_dir, batch_size=args.batch_size)
            print(json.dumps({"status": "refreshed", "build_id": report.get("build_id"), "inserted_count": report["inserted_count"], "source_document_count": report.get("source_document_count"), "source_counts": report["source_counts"], "output_dir": args.output_dir}, ensure_ascii=False, indent=2))
        elif args.command == "standardize-facts":
            report = refresh_fact_standardization(db, config, output_dir=args.output_dir, batch_size=args.batch_size)
            print(json.dumps({"status": "standardized", "build_id": report.get("build_id"), "input_build_id": report.get("input_build_id"), "standardized_count": report["standardized_count"], "verification_counts": report["verification_counts"], "output_dir": args.output_dir}, ensure_ascii=False, indent=2, default=str))
        elif args.command == "refresh-derived-facts":
            report = refresh_derived_facts(db, config, output_dir=args.output_dir, batch_size=args.batch_size)
            print(json.dumps({"status": "refreshed", "build_id": report.get("build_id"), "input_build_id": report.get("input_build_id"), "derived_count": report["derived_count"], "derived_type_counts": report["derived_type_counts"], "scope_type_counts": report.get("scope_type_counts"), "output_dir": args.output_dir}, ensure_ascii=False, indent=2, default=str))
        elif args.command == "refresh-source-definitions":
            report = refresh_source_metric_definitions(db, config, output_dir=args.output_dir)
            print(json.dumps({"status": "refreshed", "definition_count": report["definition_count"], "source_counts": report["source_counts"], "output_dir": args.output_dir}, ensure_ascii=False, indent=2, default=str))
        elif args.command == "refresh-frequency-map":
            report = refresh_time_series_frequency_map(db, config, output_dir=args.output_dir)
            print(json.dumps({"status": "refreshed", "frequency_count": report["frequency_count"], "frequency_counts": report["frequency_counts"], "output_dir": args.output_dir}, ensure_ascii=False, indent=2, default=str))
        elif args.command == "refresh-document-extraction":
            report = refresh_document_extraction(db, config, output_dir=args.output_dir)
            print(json.dumps({"status": "refreshed", "build_id": report.get("build_id"), "chunk_count": report["chunk_count"], "candidate_count": report["candidate_count"], "candidate_state_counts": report.get("candidate_state_counts"), "promotion_status_counts": report.get("promotion_status_counts"), "candidate_qa_eligible_count": report.get("candidate_qa_eligible_count"), "candidate_kg_eligible_count": report.get("candidate_kg_eligible_count"), "output_dir": args.output_dir}, ensure_ascii=False, indent=2, default=str))
        elif args.command == "enforce-quality":
            try:
                result = enforce_quality_gates(db, config)
            except QualityGateError as exc:
                print(json.dumps({"quality_gate_status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2))
                raise SystemExit(1)
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str))
        elif args.command == "enforce-fact-quality":
            try:
                result = enforce_fact_quality_gates(db, config, output_dir=args.output_dir)
            except QualityGateError as exc:
                print(json.dumps({"fact_quality_gate_status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2))
                raise SystemExit(1)
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str))
        elif args.command == "build-kg":
            report = build_kg(db, config, output_dir=args.output_dir, batch_size=args.batch_size)
            quality_status = report.get("quality", {}).get("kg_quality_gate_status")
            print(json.dumps({"status": "built" if quality_status == "passed" else "quality_failed", "kg_build_id": report.get("kg_build_id"), "input_fact_build_id": report.get("input_fact_build_id"), "input_qa_build_id": report.get("input_qa_build_id"), "node_count": report.get("node_count"), "edge_count": report.get("edge_count"), "kg_quality_gate_status": quality_status, "kg_quality_gate_failures": report.get("quality", {}).get("kg_quality_gate_failures"), "output_dir": args.output_dir}, ensure_ascii=False, indent=2, default=str))
            if quality_status != "passed":
                raise SystemExit(1)
        elif args.command == "kg-quality-report":
            report = kg_quality_report(db, kg_build_id=args.kg_build_id, output_dir=args.output_dir)
            print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str))
        elif args.command == "export-kg-jsonl":
            paths = export_kg_jsonl(db, args.output_dir, kg_build_id=args.kg_build_id)
            print(json.dumps([str(path) for path in paths], ensure_ascii=False, indent=2))
        elif args.command == "kg-retention":
            policy = config.get("kg", {}).get("retention", {})
            report = enforce_kg_retention(
                db,
                archive_dir=args.archive_dir or policy.get("archive_dir", "data/kg_archive"),
                hot_build_count=args.hot_builds or int(policy.get("hot_build_count", 2)),
                execute=args.execute,
                purge=args.purge,
                vacuum=args.vacuum,
                output_dir=args.output_dir,
                batch_size=args.batch_size,
            )
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        elif args.command == "query-kg":
            if args.mode == "neighbors":
                if not args.node_id:
                    raise ValueError("--node-id is required for neighbors mode")
                result = query_neighbors(
                    db,
                    args.node_id,
                    kg_build_id=args.kg_build_id,
                    direction=args.direction,
                    relation_type=args.relation_type,
                    limit=args.limit,
                )
            elif args.mode == "facts":
                result = query_facts(
                    db,
                    entity_id=args.entity_id,
                    metric_id=args.metric_id,
                    date_from=args.date_from,
                    date_to=args.date_to,
                    source_id=args.source_id,
                    kg_build_id=args.kg_build_id,
                    limit=args.limit,
                )
            else:
                result = query_derived_facts(
                    db,
                    derived_type=args.derived_type,
                    entity_id=args.entity_id,
                    kg_build_id=args.kg_build_id,
                    limit=args.limit,
                )
            print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        elif args.command == "build-qa-candidates":
            report = build_qa_candidates(db, config, kg_build_id=args.kg_build_id, output_dir=args.output_dir, batch_size=args.batch_size)
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        elif args.command == "generate-qa":
            report = generate_qa_samples(db, args.qa_build_id, output_dir=args.output_dir, batch_size=args.batch_size)
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        elif args.command == "validate-qa":
            report = validate_qa_samples(db, args.qa_build_id, output_dir=args.output_dir, batch_size=args.batch_size)
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        elif args.command == "split-qa":
            report = split_qa_samples(db, args.qa_build_id, output_dir=args.output_dir)
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
            if report.get("build_gate_status") != "passed":
                raise RuntimeError(f"QA build gate failed: {report.get('build_gate_failures', [])}")
        elif args.command == "export-qa-jsonl":
            report = export_qa_jsonl(db, args.qa_build_id, args.output_dir)
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        elif args.command == "qa-analysis":
            report = build_qa_diversity_report(
                db, args.qa_build_id, output_dir=args.output_dir
            )
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        elif args.command == "build-qa":
            report = build_qa(db, config, kg_build_id=args.kg_build_id, output_dir=args.output_dir, batch_size=args.batch_size)
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
            if report.get("split", {}).get("build_gate_status") != "passed":
                raise RuntimeError(f"QA build gate failed: {report.get('split', {}).get('build_gate_failures', [])}")
        elif args.command == "validate":
            passed, failed = validate_raw_objects(db)
            print(f"Validation completed: passed={passed}, failed={failed}")
    except Exception as exc:
        try:
            mark_running_builds_failed(db, str(exc))
        except Exception:
            pass
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
