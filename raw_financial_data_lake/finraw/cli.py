from __future__ import annotations

import argparse
import json

from finraw.atomic_facts import refresh_atomic_facts
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
from finraw.db.client import create_metadata_db
from finraw.entity_normalization import refresh_entity_normalization
from finraw.export import export_jsonl, export_parquet
from finraw.fact_standardization import refresh_fact_standardization
from finraw.metric_ontology import refresh_metric_ontology
from finraw.quality import QualityGateError, enforce_quality_gates
from finraw.storage import RawObjectStore
from finraw.validation import quality_report, validate_raw_objects


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a Raw Financial Data Lake.")
    parser.add_argument("--config", help="Path to config JSON.", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="Create metadata database schema.")
    sub.add_parser("seed-sources", help="Insert source registry seed rows.")

    ingest = sub.add_parser("ingest", help="Run an ingestion connector.")
    ingest.add_argument("source", choices=["sec-sample", "sec-filings", "sec-bulk", "fred", "worldbank", "imf", "cninfo", "test", "all"])
    ingest.add_argument("--dry-run", action="store_true", help="Print targets without downloading or writing data.")

    export_jsonl_parser = sub.add_parser("export-jsonl", help="Export metadata tables to JSONL.")
    export_jsonl_parser.add_argument("output_dir")

    export_parquet_parser = sub.add_parser("export-parquet", help="Export metadata tables to Parquet if pyarrow is installed.")
    export_parquet_parser.add_argument("output_dir")

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

    sub.add_parser("enforce-quality", help="Enforce configured quality gates and storage budget.")
    sub.add_parser("validate", help="Recompute checksums for saved raw objects.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = load_config(args.config)
    db = create_metadata_db(config)
    store = RawObjectStore(config["storage_root"])

    try:
        if args.command == "init-db":
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
            print(json.dumps({"status": "refreshed", "canonical_entity_count": report["canonical_entity_count"], "alias_count": report["alias_count"], "output_dir": args.output_dir}, ensure_ascii=False, indent=2))
        elif args.command == "refresh-metrics":
            report = refresh_metric_ontology(db, config, output_dir=args.output_dir)
            print(json.dumps({"status": "refreshed", "metric_count": report["metric_count"], "alias_count": report["alias_count"], "output_dir": args.output_dir}, ensure_ascii=False, indent=2))
        elif args.command == "refresh-atomic-facts":
            report = refresh_atomic_facts(db, config, output_dir=args.output_dir, batch_size=args.batch_size)
            print(json.dumps({"status": "refreshed", "inserted_count": report["inserted_count"], "source_counts": report["source_counts"], "output_dir": args.output_dir}, ensure_ascii=False, indent=2))
        elif args.command == "standardize-facts":
            report = refresh_fact_standardization(db, config, output_dir=args.output_dir, batch_size=args.batch_size)
            print(json.dumps({"status": "standardized", "standardized_count": report["standardized_count"], "verification_counts": report["verification_counts"], "output_dir": args.output_dir}, ensure_ascii=False, indent=2, default=str))
        elif args.command == "refresh-derived-facts":
            report = refresh_derived_facts(db, config, output_dir=args.output_dir, batch_size=args.batch_size)
            print(json.dumps({"status": "refreshed", "derived_count": report["derived_count"], "derived_type_counts": report["derived_type_counts"], "output_dir": args.output_dir}, ensure_ascii=False, indent=2, default=str))
        elif args.command == "enforce-quality":
            try:
                result = enforce_quality_gates(db, config)
            except QualityGateError as exc:
                print(json.dumps({"quality_gate_status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2))
                raise SystemExit(1)
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str))
        elif args.command == "validate":
            passed, failed = validate_raw_objects(db)
            print(f"Validation completed: passed={passed}, failed={failed}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
