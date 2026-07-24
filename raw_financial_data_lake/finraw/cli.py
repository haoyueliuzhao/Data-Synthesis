from __future__ import annotations

import argparse
import json
from pathlib import Path

from finraw.analysis.diversity import build_analysis_diversity_report
from finraw.analysis.export import export_analysis_jsonl
from finraw.analysis.pipeline import build_financial_analysis
from finraw.analysis.verifier import validate_analysis_samples
from finraw.artifact_retention import enforce_artifact_retention
from finraw.atomic_facts import refresh_atomic_facts
from finraw.builds import mark_running_builds_failed
from finraw.bse_discovery import discover_bse_from_strategy, write_bse_config
from finraw.cn_financial_statements import refresh_cn_financial_statements
from finraw.cn_market_universe import (
    assemble_cn_expansion_profile,
    build_a_share_universe,
    write_a_share_universe,
    write_cn_expansion_profile,
)
from finraw.cninfo_discovery import discover_cninfo_announcements, discover_cninfo_from_strategy, write_cninfo_config
from finraw.config import load_config
from finraw.connectors.cninfo import CninfoConnector
from finraw.connectors.bse import BseConnector
from finraw.connectors.fred import FredConnector
from finraw.connectors.imf import ImfSdmxConnector
from finraw.connectors.hkex import HkexConnector
from finraw.connectors.official_publications import OfficialPublicationConnector
from finraw.connectors.sec import SecBulkConnector
from finraw.connectors.sec_filings import SecFilingsConnector
from finraw.connectors.sec_sample import SecCompanyJsonConnector
from finraw.connectors.worldbank import WorldBankConnector
from finraw.coverage import build_data_coverage_report, refresh_data_coverage_report, write_coverage_outputs
from finraw.hkex_discovery import (
    assemble_hkex_expansion_profile,
    build_hkex_disclosure_config,
    write_hkex_config,
    write_hkex_expansion_profile,
)
from finraw.derived_facts import refresh_derived_facts
from finraw.document_extraction import refresh_document_extraction
from finraw.db.client import create_metadata_db
from finraw.entity_normalization import refresh_entity_normalization
from finraw.export import export_jsonl, export_layer_jsonl, export_layer_parquet, export_parquet
from finraw.layers import LAYER_TABLES, layer_manifest
from finraw.fact_quality import enforce_fact_quality_gates
from finraw.fact_universe import build_fact_universe
from finraw.fact_standardization import refresh_fact_standardization
from finraw.greater_china_quality import enforce_greater_china_quality_gates
from finraw.kg_builder import build_kg, export_kg_jsonl, kg_quality_report
from finraw.kg_retention import enforce_kg_retention
from finraw.kg_query import query_derived_facts, query_facts, query_neighbors
from finraw.metric_ontology import refresh_metric_ontology
from finraw.qa.export import export_qa_jsonl
from finraw.qa.diversity import build_qa_diversity_report
from finraw.qa.evaluation import (
    adjudicate_quality_run,
    build_empirical_report,
    run_empirical_model_evaluation,
    export_manual_review_queue,
    init_quality_evaluation,
    quality_evaluation_report,
    run_quality_evaluation,
)
from finraw.qa.finsearchcomp_alignment import (
    FINSEARCHCOMP_RAW_SHA256,
    FINSEARCHCOMP_REVISION,
    align_qa_build_to_finsearchcomp,
    analyze_official_finsearchcomp,
    freeze_finsearchcomp_dataset,
)
from finraw.qa.pattern_catalog import publish_mining_run_to_catalog
from finraw.qa.pattern_ideation import (
    generate_pattern_ideas,
    write_pattern_ideation_report,
)
from finraw.qa.pipeline import build_qa, build_qa_candidates, generate_qa_samples, split_qa_samples, validate_qa_samples
from finraw.qa.pattern_mining import (
    mine_qa_patterns,
    review_pattern_proposal,
    transition_mining_run,
)
from finraw.qa.preflight import profile_graph_patterns
from finraw.qa_cleanup import (
    PURGE_CONFIRMATION,
    default_qa_artifact_paths,
    purge_qa_history,
)
from finraw.qa_retention import enforce_qa_retention
from finraw.regional_share_audit import audit_regional_shares
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
    ingest.add_argument("source", choices=["sec-sample", "sec-filings", "sec-bulk", "fred", "worldbank", "imf", "cninfo", "bse", "hkex", "official-publications", "test", "all"])
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
    discover_cninfo.add_argument("--market", choices=["SSE", "SZSE"], help="Exchange column; inferred from the stock code when omitted.")
    discover_cninfo.add_argument("--max-pages", type=int, default=1)
    discover_cninfo.add_argument("--page-size", type=int, default=30)
    discover_cninfo.add_argument("--output", default="config/cninfo_announcements.generated.json")

    discover_batch = sub.add_parser("discover-cninfo-batch", help="Discover CNInfo announcement PDF URLs from a stock-pool strategy config.")
    discover_batch.add_argument("--strategy", required=True)
    discover_batch.add_argument("--output", default="config/cninfo_announcements.generated.json")

    discover_universe = sub.add_parser(
        "discover-a-share-universe",
        help="Build an authoritative, industry-stratified SSE/SZSE/BSE company pool.",
    )
    discover_universe.add_argument("--sse-count", type=int, default=45)
    discover_universe.add_argument("--szse-count", type=int, default=40)
    discover_universe.add_argument("--bse-count", type=int, default=15)
    discover_universe.add_argument(
        "--output", default="config/scopes/cn_a_share_authoritative_100.json"
    )

    discover_bse = sub.add_parser(
        "discover-bse-batch",
        help="Discover BSE official report PDFs from an A-share universe file.",
    )
    discover_bse.add_argument("--strategy", required=True)
    discover_bse.add_argument(
        "--output", default="config/bse_announcements.generated.json"
    )

    assemble_cn_profile = sub.add_parser(
        "assemble-cn-expansion-profile",
        help="Validate official A-share report coverage and assemble an ingestion profile.",
    )
    assemble_cn_profile.add_argument(
        "--universe",
        default="config/scopes/cn_a_share_authoritative_100.json",
    )
    assemble_cn_profile.add_argument(
        "--cninfo-manifest",
        default="config/cninfo_announcements.authoritative_100.json",
    )
    assemble_cn_profile.add_argument(
        "--bse-manifest",
        default="config/bse_announcements.authoritative_15.json",
    )
    assemble_cn_profile.add_argument(
        "--extends", default="prod_phase1_with_cninfo_generated.json"
    )
    assemble_cn_profile.add_argument(
        "--output", default="config/profiles/prod_cn_authoritative_expansion.json"
    )

    discover_hkex = sub.add_parser(
        "discover-hkex-batch",
        help="Resolve a 30-50 company HKEX pool and discover official annual reports.",
    )
    discover_hkex.add_argument("--company-count", type=int, default=40)
    discover_hkex.add_argument("--start-date", default="2020-01-01")
    discover_hkex.add_argument("--end-date")
    discover_hkex.add_argument("--minimum-annual-years", type=int, default=5)
    discover_hkex.add_argument(
        "--output", default="config/hkex_announcements.authoritative_40.json"
    )

    assemble_hkex_profile = sub.add_parser(
        "assemble-hkex-expansion-profile",
        help="Add a validated HKEX annual-report manifest to the A-share profile.",
    )
    assemble_hkex_profile.add_argument(
        "--manifest", default="config/hkex_announcements.authoritative_40.json"
    )
    assemble_hkex_profile.add_argument(
        "--extends", default="prod_cn_authoritative_expansion.json"
    )
    assemble_hkex_profile.add_argument(
        "--output", default="config/profiles/prod_greater_china_authoritative.json"
    )

    sub.add_parser("quality-report", help="Print data quality and coverage summary as JSON.")

    coverage_report = sub.add_parser("coverage-report", help="Print detailed source/entity/time/data-type coverage as JSON.")
    coverage_report.add_argument("--output-dir", help="Optional directory for JSON and Markdown coverage reports.")

    refresh_coverage = sub.add_parser("refresh-coverage-report", help="Refresh data_coverage_report table and optionally write report files.")
    refresh_coverage.add_argument("--output-dir", default="data/audit", help="Directory for JSON and Markdown coverage reports.")
    regional_share = sub.add_parser(
        "regional-share-audit",
        help="Audit international versus Greater China shares across active data layers.",
    )
    regional_share.add_argument(
        "--output-dir",
        default="data/audit/regional_share",
        help="Directory for JSON and Markdown regional share reports.",
    )
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

    cn_statements = sub.add_parser("refresh-cn-financial-statements", help="Parse and verify consolidated CNInfo PDF statement candidates.")
    cn_statements.add_argument("--output-dir", default="data/audit/fact_build/cn_statements")
    cn_statements.add_argument("--max-objects", type=int, help="Optional deterministic object limit for smoke tests; omit for configured/full input.")
    cn_statements.add_argument("--report-type", action="append", dest="report_types", help="Eligible report type; repeat to select multiple. Defaults to configured annual reports.")

    sub.add_parser("enforce-quality", help="Enforce configured raw object quality gates and storage budget.")

    enforce_fact_quality = sub.add_parser("enforce-fact-quality", help="Enforce fact-level quality gates and mark graph-ready standardized facts.")
    enforce_fact_quality.add_argument("--output-dir", default="data/audit/fact_validation", help="Directory for fact quality report files.")

    greater_china_quality = sub.add_parser(
        "enforce-greater-china-quality",
        help="Enforce company-level Greater China raw, parser, fact, and official-source coverage gates.",
    )
    greater_china_quality.add_argument(
        "--output-dir",
        default="data/audit/greater_china_validation",
        help="Directory for scoped Greater China quality report files.",
    )

    fact_universe = sub.add_parser(
        "build-fact-universe",
        help=(
            "Build a versioned, regionally stratified serving universe from "
            "graph-ready standardized facts."
        ),
    )
    fact_universe.add_argument(
        "--output-dir",
        default="data/audit/fact_universe",
        help="Directory for fact-universe manifest and quality reports.",
    )
    fact_universe.add_argument(
        "--batch-size",
        type=int,
        default=10000,
        help="Batch size for fact-universe membership inserts.",
    )

    build_kg_parser = sub.add_parser("build-kg", help="Build a versioned property graph from graph-ready facts and derived facts.")
    build_kg_parser.add_argument("--output-dir", default="data/audit/kg", help="Directory for KG build and quality reports.")
    build_kg_parser.add_argument("--batch-size", type=int, default=20000, help="Batch size for kg_nodes and kg_edges inserts.")
    build_kg_parser.add_argument(
        "--no-activate",
        action="store_true",
        help="Keep a passing KG build non-active for validation or comparison.",
    )

    kg_quality = sub.add_parser("kg-quality-report", help="Write and print KG quality checks for the active or selected KG build.")
    kg_quality.add_argument("--kg-build-id", help="Optional KG build ID. Defaults to the active KG build.")
    kg_quality.add_argument("--output-dir", default="data/audit/kg", help="Directory for KG quality report files.")

    kg_export = sub.add_parser("export-kg-jsonl", help="Export active or selected KG nodes and edges to JSONL.")
    kg_export.add_argument("output_dir")
    kg_export.add_argument("--kg-build-id", help="Optional KG build ID. Defaults to the active KG build.")

    kg_retention = sub.add_parser("kg-retention", help="Plan or execute hot/cold KG build retention.")
    kg_retention.add_argument("--hot-builds", type=int, help="Number of successful KG builds to keep in PostgreSQL.")
    kg_retention.add_argument("--preserve-build-id", action="append", default=[], help="Additional KG build ID to keep hot; may be repeated.")
    kg_retention.add_argument("--archive-dir", help="Cold archive directory. Defaults to config kg.retention.archive_dir.")
    kg_retention.add_argument("--output-dir", default="data/audit/kg_retention")
    kg_retention.add_argument("--execute", action="store_true", help="Write verified Parquet/ZSTD archives.")
    kg_retention.add_argument("--purge", action="store_true", help="Delete archived node/edge rows after verification.")
    kg_retention.add_argument("--vacuum", action="store_true", help="VACUUM graph tables after purge.")
    kg_retention.add_argument("--batch-size", type=int, default=100000)

    qa_retention = sub.add_parser("qa-retention", help="Plan or execute hot/cold QA build retention.")
    qa_retention.add_argument("--hot-builds", type=int, help="Number of recent passing non-trivial QA builds to keep hot.")
    qa_retention.add_argument("--minimum-hot-samples", type=int, help="Minimum sample count for a non-active build to qualify as hot.")
    qa_retention.add_argument("--preserve-build-id", action="append", default=[], help="Additional QA build ID to keep hot; may be repeated.")
    qa_retention.add_argument("--archive-dir", help="Cold archive directory. Defaults to config qa.retention.archive_dir.")
    qa_retention.add_argument("--output-dir", default="data/audit/qa_retention")
    qa_retention.add_argument("--execute", action="store_true", help="Write verified Parquet/ZSTD archives.")
    qa_retention.add_argument("--purge", action="store_true", help="Delete archived QA child rows after verification.")
    qa_retention.add_argument("--vacuum", action="store_true", help="VACUUM QA child tables after purge.")
    qa_retention.add_argument("--batch-size", type=int, default=50000)

    qa_purge = sub.add_parser(
        "purge-qa-history",
        help="Plan or purge all generated QA, mining/catalog, and analysis history.",
    )
    qa_purge.add_argument(
        "--execute",
        action="store_true",
        help="Execute the destructive cleanup; otherwise only write a plan.",
    )
    qa_purge.add_argument(
        "--confirm",
        help=f"Required with --execute; must equal {PURGE_CONFIRMATION}.",
    )
    qa_purge.add_argument(
        "--keep-analysis",
        action="store_true",
        help="Keep semi-open financial analysis builds and registries.",
    )
    qa_purge.add_argument(
        "--keep-registries",
        action="store_true",
        help="Keep code-rebuildable QA templates, graph patterns, signals, and analysis patterns.",
    )
    qa_purge.add_argument(
        "--keep-artifacts",
        action="store_true",
        help="Keep generated QA/analysis exports and archives on disk.",
    )
    qa_purge.add_argument(
        "--keep-audit-artifacts",
        action="store_true",
        help="Keep old QA, analysis, FinSearchComp alignment, and LLM test audit directories.",
    )
    qa_purge.add_argument(
        "--output-dir",
        default="data/audit/qa_history_cleanup",
        help="Directory for the cleanup plan or result report.",
    )

    artifact_retention = sub.add_parser(
        "artifact-retention",
        help="Plan or delete cold QA exports and verified redundant metadata JSONL.",
    )
    artifact_retention.add_argument(
        "--qa-export-root",
        action="append",
        default=[],
        help="QA export root to scan; may be repeated.",
    )
    artifact_retention.add_argument(
        "--metadata-jsonl-dir", default="data/prod_exports/jsonl"
    )
    artifact_retention.add_argument(
        "--metadata-parquet-dir", default="data/prod_exports/parquet"
    )
    artifact_retention.add_argument(
        "--output-dir", default="data/audit/artifact_retention"
    )
    artifact_retention.add_argument(
        "--execute", action="store_true", help="Delete only verified cleanup candidates."
    )

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
    qa_candidates.add_argument(
        "--pattern-catalog-release-id",
        help="Explicit immutable Pattern Catalog release to compile against the target KG.",
    )
    qa_candidates.add_argument(
        "--mining-run-id",
        help="Required explicit approved Mining Run when pattern mining is enabled.",
    )
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
    qa_split.add_argument("--no-activate", action="store_true", help="Keep a passing QA build non-active for smoke or audit runs.")

    qa_export = sub.add_parser("export-qa-jsonl", help="Export passed QA as benchmark, SFT, and trace-seed JSONL.")
    qa_export.add_argument("--qa-build-id", required=True)
    qa_export.add_argument("--output-dir", default="data/qa_exports")

    qa_analysis = sub.add_parser("qa-analysis", help="Report QA semantic diversity and KG utilization for a QA build.")
    qa_analysis.add_argument("--qa-build-id", required=True)
    qa_analysis.add_argument("--output-dir", default="data/audit/qa_analysis")

    qa_quality_init = sub.add_parser(
        "qa-quality-init",
        help="Create a version-pinned advisory financial QA quality evaluation run.",
    )
    qa_quality_init.add_argument("--qa-build-id", required=True)
    qa_quality_init.add_argument("--limit", type=int)
    qa_quality_init.add_argument(
        "--evaluation-mode",
        choices=("advisory", "calibration", "release_gate", "retrospective"),
    )

    qa_quality_evaluate = sub.add_parser(
        "qa-quality-evaluate",
        help="Run Surface and Grounded financial quality judges and aggregate results.",
    )
    qa_quality_evaluate.add_argument("--evaluation-run-id", required=True)
    qa_quality_evaluate.add_argument(
        "--output-dir", default="data/audit/qa_quality/report"
    )

    qa_quality_adjudicate = sub.add_parser(
        "qa-quality-adjudicate",
        help="Run the adversarial judge for disputed or boundary quality items.",
    )
    qa_quality_adjudicate.add_argument("--evaluation-run-id", required=True)
    qa_quality_adjudicate.add_argument(
        "--output-dir", default="data/audit/qa_quality/report"
    )

    qa_quality_empirical = sub.add_parser(
        "qa-quality-empirical",
        help="Run evidence-given L3 trials with multiple pinned respondent models.",
    )
    qa_quality_empirical.add_argument(
        "--qa-build-id", action="append", required=True
    )
    qa_quality_empirical.add_argument("--limit", type=int, default=12)
    qa_quality_empirical.add_argument(
        "--output-dir", default="data/audit/qa_quality/empirical"
    )

    qa_quality_empirical_report = sub.add_parser(
        "qa-quality-empirical-report",
        help="Rebuild a persisted L3 empirical evaluation report.",
    )
    qa_quality_empirical_report.add_argument("--empirical-run-id", required=True)
    qa_quality_empirical_report.add_argument(
        "--output-dir", default="data/audit/qa_quality/empirical"
    )

    qa_quality_report = sub.add_parser(
        "qa-quality-report",
        help="Rebuild a reproducible financial QA quality and slice report.",
    )
    qa_quality_report.add_argument("--evaluation-run-id", required=True)
    qa_quality_report.add_argument(
        "--output-dir", default="data/audit/qa_quality/report"
    )

    qa_quality_review = sub.add_parser(
        "qa-quality-review-export",
        help="Export a blind human-review queue for disputed quality items.",
    )
    qa_quality_review.add_argument("--evaluation-run-id", required=True)
    qa_quality_review.add_argument(
        "--output-dir", default="data/audit/qa_quality/review"
    )

    freeze_finsearchcomp = sub.add_parser(
        "freeze-finsearchcomp",
        help="Validate and freeze a pinned official FinSearchComp JSON release.",
    )
    freeze_finsearchcomp.add_argument(
        "--input-path",
        default="benchmarks/finsearchcomp/raw/finsearchcomp_data.json",
    )
    freeze_finsearchcomp.add_argument(
        "--output-dir", default="benchmarks/finsearchcomp/frozen"
    )
    freeze_finsearchcomp.add_argument("--revision", default=FINSEARCHCOMP_REVISION)
    freeze_finsearchcomp.add_argument(
        "--expected-sha256", default=FINSEARCHCOMP_RAW_SHA256
    )

    analyze_finsearchcomp = sub.add_parser(
        "analyze-finsearchcomp",
        help="Create deterministic native statistics and reviewable T1/T2/T3 taxonomy.",
    )
    analyze_finsearchcomp.add_argument(
        "--frozen-path",
        default="benchmarks/finsearchcomp/frozen/finsearchcomp_v1.parquet",
    )
    analyze_finsearchcomp.add_argument(
        "--output-dir", default="benchmarks/finsearchcomp/analysis"
    )

    align_finsearchcomp = sub.add_parser(
        "align-finsearchcomp",
        help="Map a passed QA build to FinSearchComp T2/T3 and report distribution gaps.",
    )
    align_finsearchcomp.add_argument("--qa-build-id", required=True)
    align_finsearchcomp.add_argument(
        "--official-taxonomy-path",
        default="benchmarks/finsearchcomp/analysis/item_taxonomy.parquet",
    )
    align_finsearchcomp.add_argument(
        "--output-dir", default="data/audit/finsearchcomp_alignment"
    )
    align_finsearchcomp.add_argument("--target-t2-count", type=int, default=3000)
    align_finsearchcomp.add_argument("--target-t3-count", type=int, default=1500)

    qa_preflight = sub.add_parser(
        "qa-pattern-preflight",
        help="Profile graph-pattern discovery against a pinned KG without creating QA rows.",
    )
    qa_preflight.add_argument("--kg-build-id", help="Optional KG build ID. Defaults to active KG.")
    qa_preflight.add_argument("--limit-per-pattern", type=int, default=500)
    qa_preflight.add_argument("--output-dir", default="data/audit/qa_pattern_preflight")

    qa_mining = sub.add_parser(
        "mine-qa-patterns",
        help="Mine high-value executable QA pattern proposals from a pinned KG build.",
    )
    qa_mining.add_argument("--kg-build-id", help="Optional KG build ID. Defaults to active KG.")
    qa_mining.add_argument("--output-dir", default="data/audit/qa_pattern_mining")

    qa_ideation = sub.add_parser(
        "ideate-qa-patterns",
        help="Ask an LLM for registry-bounded QA pattern ideas without publishing them.",
    )
    qa_ideation.add_argument(
        "--metric-id",
        action="append",
        default=[],
        help="Allowed metric ID. Repeat to pass multiple IDs; defaults to active metrics.",
    )
    qa_ideation.add_argument("--maximum-ideas", type=int, default=10)
    qa_ideation.add_argument(
        "--output-dir", default="data/audit/qa_pattern_ideation"
    )

    qa_pattern_review = sub.add_parser(
        "review-qa-pattern",
        help="Approve or reject an execution-validated mined QA pattern proposal.",
    )
    qa_pattern_review.add_argument("--proposal-id", required=True)
    qa_pattern_review.add_argument(
        "--decision", required=True, choices=("approve", "reject")
    )
    qa_pattern_review.add_argument("--reviewer", required=True)
    qa_pattern_review.add_argument("--notes")
    qa_pattern_review.add_argument(
        "--no-publish",
        action="store_true",
        help="Leave an approved proposal at reviewed_approved instead of publishing it.",
    )

    qa_catalog_publish = sub.add_parser(
        "publish-qa-pattern-catalog",
        help="Publish immutable Pattern Catalog entries from an approved Mining Run.",
    )
    qa_catalog_publish.add_argument("--mining-run-id", required=True)
    qa_catalog_publish.add_argument("--publisher", required=True)
    qa_catalog_publish.add_argument("--notes")

    qa_mining_review = sub.add_parser(
        "transition-qa-mining-run",
        help="Review, approve for QA, or supersede a completed QA Mining Run.",
    )
    qa_mining_review.add_argument("--mining-run-id", required=True)
    qa_mining_review.add_argument(
        "--target-status",
        required=True,
        choices=("reviewed", "approved_for_qa", "superseded"),
    )
    qa_mining_review.add_argument("--reviewer", required=True)
    qa_mining_review.add_argument("--notes")
    qa_mining_review.add_argument("--superseded-by-run-id")

    qa_all = sub.add_parser("build-qa", help="Run candidate, generation, validation, and split stages end to end.")
    qa_all.add_argument("--kg-build-id", help="Optional KG build ID. Defaults to active KG.")
    qa_all.add_argument(
        "--pattern-catalog-release-id",
        help="Explicit immutable Pattern Catalog release to compile against the target KG.",
    )
    qa_all.add_argument(
        "--mining-run-id",
        help="Required explicit approved Mining Run when pattern mining is enabled.",
    )
    qa_all.add_argument("--output-dir", default="data/audit/qa_build")
    qa_all.add_argument("--batch-size", type=int, default=2000)
    qa_all.add_argument("--no-activate", action="store_true", help="Keep a passing QA build non-active for smoke or audit runs.")
    qa_all.add_argument(
        "--mined-only",
        action="store_true",
        help="Build only candidates from the explicitly pinned approved Mining Run and force non-activation.",
    )
    qa_all.add_argument("--max-mined-proposals", type=int, default=100)
    qa_all.add_argument("--max-candidates-per-proposal", type=int, default=1)

    analysis_build = sub.add_parser(
        "build-analysis",
        help="Build claim-grounded semi-open financial analysis samples from a pinned KG.",
    )
    analysis_build.add_argument("--kg-build-id", help="Optional KG build ID. Defaults to active KG.")
    analysis_build.add_argument("--output-dir", default="data/audit/analysis_build")
    analysis_build.add_argument("--limit-per-pattern", type=int)
    analysis_build.add_argument(
        "--no-activate",
        action="store_true",
        help="Keep a passing analysis build non-active for validation.",
    )

    analysis_validate = sub.add_parser(
        "validate-analysis",
        help="Independently replay signals and verify evidence, claims, and conclusions.",
    )
    analysis_validate.add_argument("--analysis-build-id", required=True)

    analysis_diversity = sub.add_parser(
        "analysis-diversity",
        help="Report Analysis Pattern, Signal, Claim, Conclusion, and split diversity.",
    )
    analysis_diversity.add_argument("--analysis-build-id", required=True)
    analysis_diversity.add_argument("--output-dir", default="data/audit/analysis_build")

    analysis_export = sub.add_parser(
        "export-analysis-jsonl",
        help="Export Evidence-given benchmark, SFT, and trace-seed analysis JSONL.",
    )
    analysis_export.add_argument("--analysis-build-id", required=True)
    analysis_export.add_argument("--output-dir", default="data/analysis_exports")

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
            if args.source in {"bse", "all"}:
                connectors.append(BseConnector(db, store, config, dry_run=args.dry_run))
            if args.source in {"hkex", "all"}:
                connectors.append(HkexConnector(db, store, config, dry_run=args.dry_run))
            if args.source in {"official-publications", "all"}:
                connectors.append(
                    OfficialPublicationConnector(
                        db,
                        store,
                        config,
                        dry_run=args.dry_run,
                    )
                )
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
                market=args.market,
            )
            path = write_cninfo_config(args.output, announcements)
            print(json.dumps({"output": str(path), "announcement_count": len(announcements)}, ensure_ascii=False, indent=2))
        elif args.command == "discover-cninfo-batch":
            with open(args.strategy, "r", encoding="utf-8") as f:
                strategy = json.load(f)
            announcements = discover_cninfo_from_strategy(strategy)
            path = write_cninfo_config(args.output, announcements)
            print(json.dumps({"output": str(path), "announcement_count": len(announcements)}, ensure_ascii=False, indent=2))
        elif args.command == "discover-a-share-universe":
            universe = build_a_share_universe(
                sse_count=args.sse_count,
                szse_count=args.szse_count,
                bse_count=args.bse_count,
            )
            path = write_a_share_universe(args.output, universe)
            print(
                json.dumps(
                    {"output": str(path), **universe["universe"]},
                    ensure_ascii=False,
                    indent=2,
                )
            )
        elif args.command == "discover-bse-batch":
            with open(args.strategy, "r", encoding="utf-8") as f:
                strategy = json.load(f)
            announcements = discover_bse_from_strategy(strategy)
            path = write_bse_config(args.output, announcements)
            print(
                json.dumps(
                    {
                        "output": str(path),
                        "announcement_count": len(announcements),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        elif args.command == "assemble-cn-expansion-profile":
            profile = assemble_cn_expansion_profile(
                universe_path=args.universe,
                cninfo_manifest_path=args.cninfo_manifest,
                bse_manifest_path=args.bse_manifest,
                extends=args.extends,
            )
            path = write_cn_expansion_profile(args.output, profile)
            print(
                json.dumps(
                    {
                        "output": str(path),
                        **profile["greater_china_expansion"]["coverage_contract"],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        elif args.command == "discover-hkex-batch":
            hkex_config = build_hkex_disclosure_config(
                requested_count=args.company_count,
                start_date=args.start_date,
                end_date=args.end_date,
                minimum_annual_years=args.minimum_annual_years,
            )
            path = write_hkex_config(args.output, hkex_config)
            print(
                json.dumps(
                    {"output": str(path), **hkex_config["hkex"]["coverage"]},
                    ensure_ascii=False,
                    indent=2,
                )
            )
        elif args.command == "assemble-hkex-expansion-profile":
            profile = assemble_hkex_expansion_profile(
                manifest_path=args.manifest,
                extends=args.extends,
            )
            path = write_hkex_expansion_profile(args.output, profile)
            print(
                json.dumps(
                    {
                        "output": str(path),
                        **profile["greater_china_expansion"]["coverage_contract"][
                            "hkex"
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
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
        elif args.command == "regional-share-audit":
            report = audit_regional_shares(db, config, output_dir=args.output_dir)
            print(
                json.dumps(
                    {
                        "status": "audited",
                        "kg_build_id": report["pinned_builds"]["kg_build_id"],
                        "balance_status": report["balance_assessment"]["status"],
                        "summary_matrix": report["summary_matrix"],
                        "written_files": report.get("written_files", []),
                    },
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
            )
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
        elif args.command == "refresh-cn-financial-statements":
            report = refresh_cn_financial_statements(
                db,
                config,
                output_dir=args.output_dir,
                max_objects=args.max_objects,
                report_types=tuple(args.report_types) if args.report_types else None,
            )
            print(json.dumps({"status": "refreshed", "build_id": report["build_id"], "object_count": report["object_count"], "parsed_object_count": report["parsed_object_count"], "candidate_count": report["candidate_count"], "promotion_approved_count": report["promotion_approved_count"], "output_dir": args.output_dir}, ensure_ascii=False, indent=2, default=str))
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
        elif args.command == "enforce-greater-china-quality":
            try:
                result = enforce_greater_china_quality_gates(
                    db, config, output_dir=args.output_dir
                )
            except QualityGateError as exc:
                print(
                    json.dumps(
                        {
                            "greater_china_quality_gate_status": "failed",
                            "error": str(exc),
                            "output_dir": args.output_dir,
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                raise SystemExit(1)
            print(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                    default=str,
                )
            )
        elif args.command == "build-fact-universe":
            report = build_fact_universe(
                db,
                config,
                output_dir=args.output_dir,
                batch_size=args.batch_size,
            )
            print(
                json.dumps(
                    {
                        "status": (
                            "built"
                            if report.get("quality_status") == "passed"
                            else "quality_failed"
                        ),
                        "universe_build_id": report.get("universe_build_id"),
                        "input_fact_build_id": report.get("input_fact_build_id"),
                        "target_greater_china_share": report.get(
                            "target_greater_china_share"
                        ),
                        "actual_greater_china_share": report.get(
                            "actual_greater_china_share"
                        ),
                        "member_distribution": report.get("member_distribution"),
                        "quality_failures": report.get("quality_failures"),
                        "output_dir": args.output_dir,
                    },
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
            )
            if report.get("quality_status") != "passed":
                raise SystemExit(1)
        elif args.command == "build-kg":
            report = build_kg(
                db,
                config,
                output_dir=args.output_dir,
                batch_size=args.batch_size,
                activate=not args.no_activate,
            )
            quality_status = report.get("quality", {}).get("kg_quality_gate_status")
            print(json.dumps({"status": "built" if quality_status == "passed" else "quality_failed", "kg_build_id": report.get("kg_build_id"), "input_fact_build_id": report.get("input_fact_build_id"), "input_qa_build_id": report.get("input_qa_build_id"), "node_count": report.get("node_count"), "edge_count": report.get("edge_count"), "activation_requested": report.get("activation_requested"), "is_active": report.get("is_active"), "kg_quality_gate_status": quality_status, "kg_quality_gate_failures": report.get("quality", {}).get("kg_quality_gate_failures"), "output_dir": args.output_dir}, ensure_ascii=False, indent=2, default=str))
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
                preserve_build_ids=args.preserve_build_id,
                execute=args.execute,
                purge=args.purge,
                vacuum=args.vacuum,
                output_dir=args.output_dir,
                batch_size=args.batch_size,
            )
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        elif args.command == "qa-retention":
            policy = config.get("qa", {}).get("retention", {})
            report = enforce_qa_retention(
                db,
                archive_dir=args.archive_dir or policy.get("archive_dir", "data/qa_archive"),
                hot_build_count=args.hot_builds if args.hot_builds is not None else int(policy.get("hot_build_count", 1)),
                minimum_hot_sample_count=args.minimum_hot_samples if args.minimum_hot_samples is not None else int(policy.get("minimum_hot_sample_count", 100)),
                preserve_build_ids=args.preserve_build_id,
                execute=args.execute,
                purge=args.purge,
                vacuum=args.vacuum,
                output_dir=args.output_dir,
                batch_size=args.batch_size,
            )
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        elif args.command == "purge-qa-history":
            project_root = Path(__file__).resolve().parents[1]
            artifact_paths = []
            if not args.keep_artifacts:
                artifact_paths = default_qa_artifact_paths(
                    project_root,
                    include_analysis=not args.keep_analysis,
                    include_audit=not args.keep_audit_artifacts,
                    exclude_paths=[args.output_dir],
                )
            report = purge_qa_history(
                db,
                project_root=project_root,
                include_analysis=not args.keep_analysis,
                include_registries=not args.keep_registries,
                artifact_paths=artifact_paths,
                execute=args.execute,
                confirmation=args.confirm,
                output_dir=args.output_dir,
            )
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        elif args.command == "artifact-retention":
            report = enforce_artifact_retention(
                db,
                qa_export_roots=args.qa_export_root
                or ["data/qa_exports", "data/qa_exports_v2_smoke"],
                metadata_jsonl_dir=args.metadata_jsonl_dir,
                metadata_parquet_dir=args.metadata_parquet_dir,
                output_dir=args.output_dir,
                execute=args.execute,
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
            report = build_qa_candidates(
                db,
                config,
                kg_build_id=args.kg_build_id,
                mining_run_id=args.mining_run_id,
                pattern_catalog_release_id=args.pattern_catalog_release_id,
                output_dir=args.output_dir,
                batch_size=args.batch_size,
            )
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        elif args.command == "generate-qa":
            report = generate_qa_samples(db, args.qa_build_id, output_dir=args.output_dir, batch_size=args.batch_size)
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        elif args.command == "validate-qa":
            report = validate_qa_samples(db, args.qa_build_id, output_dir=args.output_dir, batch_size=args.batch_size)
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        elif args.command == "split-qa":
            report = split_qa_samples(
                db,
                args.qa_build_id,
                output_dir=args.output_dir,
                activate=not args.no_activate,
            )
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
        elif args.command == "qa-quality-init":
            report = init_quality_evaluation(
                db,
                config,
                args.qa_build_id,
                limit=args.limit,
                evaluation_mode=args.evaluation_mode,
            )
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        elif args.command == "qa-quality-evaluate":
            report = run_quality_evaluation(
                db, args.evaluation_run_id, output_dir=args.output_dir
            )
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        elif args.command == "qa-quality-adjudicate":
            report = adjudicate_quality_run(
                db, args.evaluation_run_id, output_dir=args.output_dir
            )
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        elif args.command == "qa-quality-empirical":
            report = run_empirical_model_evaluation(
                db,
                config,
                args.qa_build_id,
                limit=args.limit,
                output_dir=args.output_dir,
            )
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        elif args.command == "qa-quality-empirical-report":
            report = build_empirical_report(
                db, args.empirical_run_id, output_dir=args.output_dir
            )
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        elif args.command == "qa-quality-report":
            report = quality_evaluation_report(
                db, args.evaluation_run_id, output_dir=args.output_dir
            )
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        elif args.command == "qa-quality-review-export":
            report = export_manual_review_queue(
                db, args.evaluation_run_id, args.output_dir
            )
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        elif args.command == "freeze-finsearchcomp":
            report = freeze_finsearchcomp_dataset(
                args.input_path,
                args.output_dir,
                revision=args.revision,
                expected_sha256=args.expected_sha256,
            )
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        elif args.command == "analyze-finsearchcomp":
            report = analyze_official_finsearchcomp(args.frozen_path, args.output_dir)
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        elif args.command == "align-finsearchcomp":
            report = align_qa_build_to_finsearchcomp(
                db,
                args.qa_build_id,
                args.official_taxonomy_path,
                args.output_dir,
                target_t2_count=args.target_t2_count,
                target_t3_count=args.target_t3_count,
                difficulty_audit_policy=dict(
                    config.get("qa", {})
                    .get("benchmark_alignment", {})
                    .get("difficulty_cross_audit", {})
                ),
                contamination_audit_policy=dict(
                    config.get("qa", {})
                    .get("benchmark_alignment", {})
                    .get("contamination_audit", {})
                ),
            )
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        elif args.command == "qa-pattern-preflight":
            report = profile_graph_patterns(
                db,
                config,
                kg_build_id=args.kg_build_id,
                limit_per_pattern=args.limit_per_pattern,
                output_dir=args.output_dir,
            )
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        elif args.command == "mine-qa-patterns":
            report = mine_qa_patterns(
                db,
                config,
                kg_build_id=args.kg_build_id,
                output_dir=args.output_dir,
            )
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        elif args.command == "ideate-qa-patterns":
            metric_ids = sorted(set(args.metric_id))
            if not metric_ids:
                metric_ids = [
                    str(row["metric_id"])
                    for row in db.fetchall(
                        """
                        SELECT metric_id
                        FROM metrics
                        WHERE is_active = 1
                        ORDER BY metric_id
                        LIMIT 100
                        """
                    )
                ]
            generation = dict(
                config.get("qa", {}).get("question_generation", {}) or {}
            )
            report = generate_pattern_ideas(
                metric_ids,
                {
                    "maximum_ideas": args.maximum_ideas,
                    "llm": generation.get("llm") or {},
                },
            )
            output = write_pattern_ideation_report(report, args.output_dir)
            report["output"] = str(output)
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        elif args.command == "review-qa-pattern":
            report = review_pattern_proposal(
                db,
                args.proposal_id,
                decision=args.decision,
                reviewer=args.reviewer,
                notes=args.notes,
                publish=not args.no_publish,
            )
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        elif args.command == "publish-qa-pattern-catalog":
            report = publish_mining_run_to_catalog(
                db,
                args.mining_run_id,
                publisher=args.publisher,
                notes=args.notes,
            )
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        elif args.command == "transition-qa-mining-run":
            report = transition_mining_run(
                db,
                args.mining_run_id,
                target_status=args.target_status,
                reviewer=args.reviewer,
                notes=args.notes,
                superseded_by_run_id=args.superseded_by_run_id,
            )
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        elif args.command == "build-qa":
            if args.mined_only:
                qa_config = config.setdefault("qa", {})
                for key in qa_config.get("quotas", {}):
                    qa_config["quotas"][key] = 0
                for key in qa_config.get("derived_quotas", {}):
                    qa_config["derived_quotas"][key] = 0
                qa_config.setdefault("graph_patterns", {})["enabled"] = False
                mining = qa_config.setdefault("pattern_mining", {})
                mining.update(
                    {
                        "enabled": True,
                        "auto_run": False,
                        "max_proposals": max(args.max_mined_proposals, 1),
                        "max_candidates_per_proposal": max(
                            args.max_candidates_per_proposal, 1
                        ),
                    }
                )
                gate = qa_config.setdefault("quality_gate", {})
                gate["critical_tasks"] = {}
                gate["minimum_graph_pattern_samples"] = {}
                gate["minimum_graph_pattern_eligibility_rate"] = 0
                gate["minimum_graph_feature_coverage"] = 0
                gate["minimum_unique_operation_sequences"] = 1
            report = build_qa(
                db,
                config,
                kg_build_id=args.kg_build_id,
                mining_run_id=args.mining_run_id,
                pattern_catalog_release_id=args.pattern_catalog_release_id,
                output_dir=args.output_dir,
                batch_size=args.batch_size,
                activate=not args.no_activate and not args.mined_only,
            )
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
            if report.get("split", {}).get("build_gate_status") != "passed":
                raise RuntimeError(f"QA build gate failed: {report.get('split', {}).get('build_gate_failures', [])}")
        elif args.command == "build-analysis":
            report = build_financial_analysis(
                db,
                config,
                kg_build_id=args.kg_build_id,
                output_dir=args.output_dir,
                limit_per_pattern=args.limit_per_pattern,
                activate=not args.no_activate,
            )
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
            if report.get("build_gate_status") != "passed":
                raise RuntimeError(
                    f"Analysis build gate failed: {report.get('build_gate_failures', [])}"
                )
        elif args.command == "validate-analysis":
            report = validate_analysis_samples(db, args.analysis_build_id)
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
            if report.get("quality_status") != "passed":
                raise RuntimeError(
                    f"Analysis validation failed: {report.get('failure_counts', {})}"
                )
        elif args.command == "analysis-diversity":
            report = build_analysis_diversity_report(
                db,
                args.analysis_build_id,
                output_dir=args.output_dir,
            )
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        elif args.command == "export-analysis-jsonl":
            report = export_analysis_jsonl(
                db,
                args.analysis_build_id,
                args.output_dir,
            )
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
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
