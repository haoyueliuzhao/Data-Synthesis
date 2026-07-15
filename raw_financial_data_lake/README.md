# Raw Financial Data Lake + Fact Build Pipeline

This repository started as a traceable **Raw Financial Data Lake** for SEC, FRED, World Bank, IMF, and CNInfo data. It now also contains downstream fact-building, validation, derived-fact, and document-candidate tooling.

The important boundary is:

```text
raw_lake keeps original source material.
fact_build / fact_validation / qa_ready consume raw_lake outputs but must not mutate raw source material.
```





## Source Documents

Document availability is stored in `source_documents`, not `atomic_facts`. SEC filing HTML/TXT and CNInfo PDF records are indexed with entity, source, form/report type, period end, filing date, raw object, storage URI, original URL, and status. `atomic_facts` should contain accepted numeric or string facts only. Document-derived numeric evidence remains in `candidate_facts` until explicitly validated and promoted.

`candidate_facts` are governed by an explicit state machine: `parsed -> matched_to_metric -> evidence_verified -> cross_checked -> promoted_to_atomic_fact`. The current document extraction command only creates `parsed` or `matched_to_metric` candidates and sets `qa_eligible = 0` and `kg_eligible = 0`. Candidate rows must not feed KG or QA directly; a future promote command has to verify evidence, cross-check values, and create accepted `atomic_facts`.

## SEC XBRL Fact Selection

SEC `companyfacts` values are treated as candidates before becoming atomic facts. The extractor groups candidates by entity, metric, unit, period, fiscal period, and duration, then chooses a canonical candidate using SEC-specific priority: annual facts prefer 10-K/20-F/40-F over 10-Q, quarter facts prefer 10-Q, matching calendar frames are preferred, suitable annual/quarter durations are preferred, and later filed dates break ties. Amended forms are retained only when they win their group and are marked in notes.

For period-flow quarterly data, YTD durations are labeled such as `Q2_YTD` or `Q3_YTD`; derived quarterly calculations only consume true `Q1`-`Q4` single-period rows.

## Deterministic Record And Fact IDs

Raw records and stable facts must be reproducible across reruns. Connectors use `stable_raw_record_id(source_id, raw_object_id, record_type, record_key)` instead of UUIDs. Atomic `stable_fact_id` values are derived from source business keys such as entity, metric, accession number, concept, unit, period, realtime window, and value. They must not depend on `raw_record_id`, job IDs, or build IDs.

Build-scoped row IDs may include `build_id`, but stable IDs are the reproducibility anchor for deduplication, derived facts, KG, and QA references.

## Build Versioning

Downstream refresh commands now use build versioning instead of destructive rebuilds. A run writes to `pipeline_builds`, marks old active rows inactive, and inserts new rows with `build_id`, `is_active`, and `superseded_by`. Atomic facts keep a `stable_fact_id`; the row-level `fact_id` is versioned as `stable_fact_id__build_id`. Derived facts and document candidate facts follow the same pattern with stable IDs plus build-scoped IDs.

This means KG and QA outputs can bind to a stable build version while newer refreshes continue to run.

## Logical Layers

The code can live in one repo, but tables, commands, reports, and exports are logically separated into five layers. See [Layered Architecture](docs/layered_architecture.md).

```text
Layer 1: raw_lake
  source_registry / ingestion_jobs / raw_objects / raw_records / snapshots

Layer 2: fact_build
  canonical_entities / metrics / source_documents / atomic_facts / standardized_facts / document candidates

Layer 3: fact_validation
  source definitions / frequency map / comparability fields / fact_quality_checks / graph_ready gates / conflict support

Layer 4: qa_ready
  derived_facts / kg_builds / kg_nodes / kg_edges / kg_quality_checks / kg_archives; consumes graph_ready standardized facts only

Layer 5: qa_build
  qa_builds / qa_templates / qa_candidates / qa_samples / qa_evidence_paths / qa_quality_checks
```

Print the machine-readable manifest:

```bash
python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json layers
```

## Quick Start: Raw Lake Only

```bash
cd "/workspace/Data Synthesis/raw_financial_data_lake"
python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json init-db
python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json seed-sources
python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json ingest all --dry-run
```

Run real ingestion selectively:

```bash
python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json ingest sec-bulk
FRED_API_KEY=your_key python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json ingest fred
python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json ingest worldbank
python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json ingest imf
python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json ingest cninfo
```

Raw lake outputs:

```text
data/fin_raw/
PostgreSQL metadata tables: source_registry, ingestion_jobs, raw_objects, raw_records, source_entities, raw_dataset_snapshots
```

## Build Downstream Layers

After raw ingestion, run downstream layers explicitly:

```bash
# Layer 2: fact_build
python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json refresh-entities --output-dir data/audit/fact_build
python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json refresh-metrics --output-dir data/audit/fact_build

# Layer 3 metadata used by standardize-facts
python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json refresh-source-definitions --output-dir data/audit/fact_validation
python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json refresh-frequency-map --output-dir data/audit/fact_validation

# Layer 2 facts carrying Layer 3 definition/comparability metadata
python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json refresh-atomic-facts --output-dir data/audit/fact_build
python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json standardize-facts --output-dir data/audit/fact_build
python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json refresh-document-extraction --output-dir data/audit/fact_build

# Layer 3 quality gate
python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json enforce-fact-quality --output-dir data/audit/fact_validation

# Layer 4: qa_ready
# Consumes standardized_facts where graph_ready = 1.
python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json refresh-derived-facts --output-dir data/audit/qa_ready
python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json build-kg --output-dir data/audit/kg
python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json kg-quality-report --output-dir data/audit/kg
python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json export-kg-jsonl data/kg_exports/jsonl

# Indexed serving queries (do not scan JSONL)
python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json query-kg facts --entity-id AAPL_US --metric-id revenue --limit 20
python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json query-kg derived --derived-type multi_year_argmax --entity-id AAPL_US --limit 20
python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json query-kg neighbors --node-id entity:AAPL_US --direction out --limit 20

# Dry-run first; execute archives to Parquet/ZSTD and purges only after checksum verification.
python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json kg-retention --hot-builds 2 --archive-dir data/kg_archive
python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json kg-retention --hot-builds 2 --archive-dir data/kg_archive --execute --purge --vacuum

# Layer 5: deterministic QA build pinned to a validated KG version
# Read-only matcher preflight: reports volume, fill rate, distribution, and SQL time.
python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json qa-pattern-preflight --kg-build-id kg_20260711_062123_bc4b4394 --limit-per-pattern 500 --output-dir data/audit/qa_pattern_preflight_v4
# Pattern mining requires an explicit approved_for_qa Mining Run; there is no implicit latest-run fallback.
python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json build-qa --kg-build-id kg_20260711_062123_bc4b4394 --mining-run-id qamining_xxx --output-dir data/audit/qa_build
python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json export-qa-jsonl --qa-build-id qa_build_20260712_023651_7adad081 --output-dir data/qa_exports
```

`build-qa` executes candidate construction, deterministic canonical question/answer generation, independent Decimal recomputation, relation-aware KG evidence validation, fixed-cutoff semantic-cluster splitting, and quality-gated activation. Share, ranking, and industry-ranking tasks now retain three separate payloads: the original KG `derived_payload`, the complete-scope `recomputed_payload`, and the final QA `answer_payload`. Evidence is stored as a structured subgraph with adjacency edges and connected components, while legacy `ordered_node_ids` and `ordered_edge_ids` remain compatibility aliases. A candidate is rejected with `qa_recompute_mismatch` when the KG DerivedFact output does not match the complete-scope recomputation; top-k ranking answers are never silently overwritten. LLM paraphrasing is disabled by default and never computes answers. Only a `ready` build with a passed build gate can be exported.

The active production QA build `qa_build_20260712_023651_7adad081` is pinned to KG V3 `kg_20260711_062123_bc4b4394`. It produced 68,231 candidates, rejected 4,010 DerivedFact recomputation mismatches, and exported 64,221 validated canonical samples. The split contains 41,213 train, 210 train_complex, 5,102 dev, 31 dev_complex, 5,211 standard test, 3,205 entity holdout, 9,174 temporal holdout, and 75 test_complex rows. Complex semantic groups are assigned deterministically 70/10/20 to train_complex/dev_complex/test_complex, while entity and temporal holdouts remain separate. All 64,221 samples passed `source_fact_coverage`, `derived_input_edge_coverage`, `scope_fact_coverage`, and `evidence_component_count`. Benchmark and Trace Seed outputs are written per split; SFT exports `sft/train.jsonl` and `sft/train_complex.jsonl`, preventing evaluation leakage while retaining complex-task training coverage.

`candidate_facts` are reviewable document-derived candidates. They are not accepted facts and are not promoted into `atomic_facts` without explicit validation. Fact quality gates report candidate state counts and fail if any active candidate is marked `qa_eligible` or `kg_eligible`.

`standardized_facts` carry `source_definition_id`, `frequency`, `seasonal_adjustment`, `vintage_policy`, `is_forecast`, and `comparability_level`. They also carry two verification group IDs: `raw_equivalence_group_id` for strict same-source/concept duplicate checks, and `semantic_equivalence_group_id` for cross-source entity/metric/period/unit/currency comparison. `conflict_group_id` is kept as a compatibility pointer to the group that produced a conflict or source-definition mismatch. A shared `metric_id` is not enough for cross-source verification; facts with matching values but incompatible source definitions are marked `source_definition_mismatch`, not `cross_verified`.

`derived_facts` carry explicit QA scope metadata: `scope_type`, `scope_id`, `scope_definition`, `scope_entity_ids`, and `scope_source`. In addition to YoY/QoQ/difference/ratio/share, the current build supports complete 5/10-year extrema, frequency-aware rolling extrema, FRED full-series extrema, SIC-industry rankings, explicit multi-condition screening, and conservative long-window returns for the broad U.S. dollar index. Historical derivations exclude observations marked as forecasts. Index-constituent rankings remain disabled until authoritative constituent history is ingested.

`build-kg` creates a versioned property graph inside PostgreSQL/SQLite before any Neo4j export. KG schema v3 pins the exact entity, metric, source-definition, document, standardized-fact, and derived-fact build IDs. TimePeriod nodes connect to CalendarYear, CalendarMonth, CalendarQuarter, entity-specific FiscalYear, or cross-entity FiscalYearLabel nodes. It consumes only graph-ready facts and validated derived facts from the pinned builds; `candidate_facts` remain excluded.

PostgreSQL is the indexed query-serving layer through `query-kg`; JSONL is only an interchange artifact. `kg-retention` keeps the active and previous successful builds hot, archives older graphs as checksum-verified Parquet/ZSTD, and purges PostgreSQL rows only after archive verification.

A selected historical `kg_build_id` can still be quality-checked and exported after it is superseded. `kg_builds.is_active` selects the current graph; node/edge `is_active` records whether that build materialization is valid, so version activation does not rewrite millions of historical rows.

## Layered Exports

Full exports remain available:

```bash
python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json export-jsonl data/prod_exports/jsonl
python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json export-parquet data/prod_exports/parquet
```

Prefer layer exports when handing data to downstream consumers:

```bash
python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json export-layer-jsonl raw_lake data/layered_exports/raw_lake/jsonl
python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json export-layer-jsonl fact_build data/layered_exports/fact_build/jsonl
python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json export-layer-jsonl fact_validation data/layered_exports/fact_validation/jsonl
python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json export-layer-jsonl qa_ready data/layered_exports/qa_ready/jsonl
python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json export-layer-jsonl qa_build data/layered_exports/qa_build/jsonl
```

## FRED API Key

FRED ingestion reads the API key from `FRED_API_KEY` first, then from ignored local secrets in `config/local_secrets.json`:

```json
{
  "fred": {
    "api_key": "your_32_character_key"
  }
}
```

Do not put API keys in committed config files.

## Phase 1 Scale Profiles

```text
config/profiles/dev.json
config/profiles/test.json
config/profiles/prod_phase1.json
config/profiles/prod_phase1_with_cninfo_generated.json

config/scopes/sec_us_100.json
config/scopes/fred_50.json
config/scopes/worldbank_20x20.json
config/scopes/imf_datamapper_weo_targets.json
config/scopes/cninfo_a_share_strategy.json
config/layers/layers.json
```

Production PostgreSQL profile expects `DATABASE_URL` or an explicit `metadata_backend.dsn`.

## Invariants

- Raw objects and raw records preserve source material and provenance.
- Rebuilding entity, metric, fact, validation, or derived layers must not modify raw source files.
- Candidate facts from documents remain candidates until explicitly validated.
- Derived facts should consume standardized facts with acceptable validation states only.
- Source definition mismatch is a comparability signal, not raw data corruption.

Runbook: [docs/phase1_runbook.md](docs/phase1_runbook.md).
Storage budget: [docs/storage_budget.md](docs/storage_budget.md).
