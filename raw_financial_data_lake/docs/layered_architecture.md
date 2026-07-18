# Layered Architecture

The repository now contains multiple pipeline stages, but they are logically separated into six data layers. The raw lake remains the stable provenance layer; downstream facts, validation, and QA-ready artifacts consume it without changing the original raw objects.

## Layer 1: raw_lake

Purpose: preserve source material completely and reproducibly.

Tables:

- `source_registry`
- `ingestion_jobs`
- `raw_objects`
- `raw_records`
- `source_entities`
- `raw_dataset_snapshots`
- `data_coverage_report`

Allowed commands:

- `init-db`
- `seed-sources`
- `ingest ...`
- `validate`
- `quality-report`
- `coverage-report`
- `refresh-coverage-report`

This layer should never depend on canonical entities, metric ontology, standardized units, or derived calculations.

## Layer 2: fact_build

Purpose: transform raw records into canonical factual structures.

Tables:

- `canonical_entities`
- `entity_alias_map`
- `metrics`
- `metric_alias_map`
- `atomic_facts`
- `standardized_facts`
- `source_documents`
- `document_text_chunks`
- `raw_extracted_tables`
- `candidate_facts`

Important boundary: `candidate_facts` are not accepted facts. They are reviewable evidence candidates, especially for SEC HTML/PDF-derived material. Their state machine is `parsed -> matched_to_metric -> evidence_verified -> cross_checked -> promoted_to_atomic_fact`; only a future explicit promotion workflow may create `atomic_facts`. Current document extraction leaves candidates non-eligible for KG/QA.

## Layer 3: fact_validation

Purpose: explain, validate, and qualify facts before they can feed KG or QA generation.

Tables:

- `source_metric_definitions`
- `time_series_frequency_map`
- `fact_quality_checks`

This layer records source definitions, frequency/vintage assumptions, conflicts, source definition mismatches, warnings, and validation statuses. `standardized_facts` must carry `source_definition_id`, `frequency`, `seasonal_adjustment`, `vintage_policy`, `is_forecast`, and `comparability_level` so KG/QA builders do not treat same-named metrics from different sources as automatically comparable. This layer also owns the fact-level quality gate that sets `standardized_facts.graph_ready` and writes `fact_quality_report.json` / `fact_quality_report.md`.

## Layer 4: qa_ready

Purpose: prepare validated derived facts and a versioned property graph for downstream QA construction.

Tables:

- `derived_facts`
- `kg_builds`
- `kg_nodes`
- `kg_edges`
- `kg_quality_checks`
- `kg_archives`

KG is first represented as an auditable property graph in the metadata database. It consumes only graph-ready standardized facts, active validated derived facts, source documents, raw objects, source definitions, canonical entities/securities, metrics, and source registry rows. `candidate_facts` are explicitly excluded until a future promotion workflow creates accepted atomic facts.

`derived_facts` must preserve the semantic scope of the calculation. Every row carries `scope_type`, `scope_id`, `scope_definition`, `scope_entity_ids`, and `scope_source`. This is especially important for ranking/share facts: a ranking over the configured SEC 100-company universe is not the same as a ranking over the S&P 500, Nasdaq 100, all listed companies, or a World Bank income group.

## Layer 5: qa_build

Purpose: construct deterministic, versioned QA datasets from a pinned, quality-passed KG build.

Tables:

- `qa_builds`
- `qa_templates`
- `qa_candidates`
- `qa_samples`
- `qa_evidence_paths`
- `qa_quality_checks`

The QA layer follows `KG path -> canonical semantics -> programmatic answer -> independent recomputation -> quality gates -> semantic-group split -> export`. LLM paraphrasing is optional and disabled by default; it may change wording only, never entities, metrics, time scope, calculation scope, units, or answers.

Every QA build pins the exact KG, fact, derived, entity, metric, source-definition, and document build IDs. Rejected candidates and samples remain available for audit, while only validated samples receive dataset splits and enter Benchmark, SFT, or Trace Seed exports. Provenance evidence may cite source facts, raw objects, and KG paths; page-level text evidence is not claimed until an explicit Fact-to-EvidenceChunk relation exists.

## Layer 6: analysis_build

Purpose: construct semi-open, claim-grounded financial analysis datasets beside the closed-form QA compiler.

Tables:

- `analysis_builds`
- `financial_signal_specs`
- `financial_signal_instances`
- `analysis_patterns`
- `analysis_pattern_proposals`
- `analysis_pattern_catalog_releases`
- `analysis_pattern_catalog_entries`
- `analysis_candidates`
- `analysis_evidence_bundles`
- `analysis_claim_plans`
- `analysis_samples`
- `analysis_quality_checks`

The analysis layer follows `pinned KG -> recomputable Signal -> Evidence Bundle -> Claim Plan -> Valid Conclusion Set -> claim-level verification -> split/export`. It does not reuse `qa_samples`, because correctness is evaluated against supported Claims and bounded conclusions rather than a single exact answer. Unsupported numbers, causal explanations, forecasts, investment recommendations, and target prices fail closed. See [Financial Analysis Compiler](financial_analysis_compiler.md).

## Commands

Print the machine-readable layer manifest:

```bash
python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json layers
```

Export a single layer:

```bash
python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json \
  export-layer-jsonl raw_lake data/layered_exports/raw_lake/jsonl

python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json \
  export-layer-parquet fact_build data/layered_exports/fact_build/parquet
```

Run fact-level gates before building QA-ready artifacts:

```bash
python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json \
  enforce-fact-quality --output-dir data/audit/fact_validation

python -m finraw.cli --config config/profiles/prod_phase1_with_cninfo_generated.json \
  refresh-derived-facts --output-dir data/audit/qa_ready
```

The older `export-jsonl` and `export-parquet` commands remain available for full-database snapshots.

## Source Documents

Document availability is stored in `source_documents`, not `atomic_facts`. SEC filing HTML/TXT and CNInfo PDF records are indexed with entity, source, form/report type, period end, filing date, raw object, storage URI, original URL, and status. `atomic_facts` should contain accepted numeric or string facts only. Document-derived numeric evidence remains in `candidate_facts` until explicitly validated and promoted.

## Source Definition And Comparability

`metric_id` names the canonical metric, but source-specific definitions decide whether facts can be cross-verified or compared. `source_metric_definitions` stores the source/concept definition, frequency policy, vintage policy, forecast flag, and comparability level. `time_series_frequency_map` stores FRED series frequency and seasonal adjustment.

`standardize-facts` copies these fields onto each `standardized_facts` row. It also writes two separate group IDs so validation can distinguish strict duplication from semantic cross-source comparison:

- `raw_equivalence_group_id`: entity, metric, period, unit/currency, source, source definition, and source field/concept. This catches same-source or same-concept duplicate values without relying on source ordering.
- `semantic_equivalence_group_id`: entity, metric, period, and normalized unit/currency. This lets SEC companyfacts, future inline XBRL/HTML facts, FRED, World Bank, IMF, or other compatible sources meet in the same verification group even when source concepts differ.

`conflict_group_id` remains as a compatibility field and points to the raw or semantic group that produced the current conflict or source-definition mismatch. `enforce-fact-quality` requires `source_definition_id`; missing definitions are not graph-ready. Matching values across incompatible source definitions are marked `source_definition_mismatch` instead of `cross_verified`.

`metric_alias_map` should contain strict aliases only. Related or tempting terms, such as current vs non-current long-term debt, belong in metric `related_terms`/notes and must not drive automatic mapping.

## SEC XBRL Fact Selection

SEC `companyfacts` values are treated as candidates before becoming atomic facts. The extractor groups candidates by entity, metric, unit, period, fiscal period, and duration, then chooses a canonical candidate using SEC-specific priority: annual facts prefer 10-K/20-F/40-F over 10-Q, quarter facts prefer 10-Q, matching calendar frames are preferred, suitable annual/quarter durations are preferred, and later filed dates break ties. Amended forms are retained only when they win their group and are marked in notes.

For period-flow quarterly data, YTD durations are labeled such as `Q2_YTD` or `Q3_YTD`; derived quarterly calculations only consume true `Q1`-`Q4` single-period rows.

## Deterministic IDs

`raw_record_id` is deterministic and based on `source_id`, `raw_object_id`, `record_type`, and `record_key`. It must not include UUIDs. `stable_fact_id` must be based on financial/source business keys, not `raw_record_id`, so repeated ingestion of the same raw object cannot create a different fact identity.

## Build Versioning

Refresh commands for entity, metric, atomic fact, standardized fact, derived fact, and document extraction layers are append/version oriented. They do not physically delete downstream data. Each run creates a row in `pipeline_builds` and writes a `build_id` to generated rows. Previously active rows are marked `is_active = 0` and `superseded_by = <new_build_id>`.

Stable content identifiers are preserved separately where needed:

- `atomic_facts.stable_fact_id` keeps the content-derived fact identity.
- `atomic_facts.fact_id` is versioned as `stable_fact_id__build_id`.
- `standardized_facts` keeps the same versioned `fact_id` as its atomic input.
- `derived_facts.stable_derived_id` keeps the calculation identity, while `derived_id` is versioned by the QA-ready build.
- `candidate_facts.stable_candidate_id` preserves document candidate identity so manual review history is not physically erased by a rebuild.

KG and QA artifacts should bind to a specific build, for example `qa_ready_20260709_...`, instead of assuming the latest active facts are stable forever.

## Invariants

- Raw objects and raw records are append/provenance oriented.
- Refreshing fact-build and QA-ready layers must create a new build instead of deleting historical facts.
- Rebuilding entity, metric, fact, validation, or derived layers must not modify raw objects.
- Candidate document facts must not feed `derived_facts`, KG, or QA while `qa_eligible = 0` / `kg_eligible = 0`; promotion must create accepted `atomic_facts` through explicit validation.
- `derived_facts`, KG, and QA generation should consume `standardized_facts` only where `graph_ready = 1`.
- Ranking and share derived facts must expose their scope explicitly; QA generation should include that scope in the question wording.
- Every graph-ready standardized fact must have a `source_definition_id`; same `metric_id` alone is not sufficient comparability evidence.
- Source definition mismatch is not a data corruption signal; it means values are comparable only with extra source-definition context.

## KG Quality Gates

`build-kg` writes `kg_builds`, `kg_nodes`, `kg_edges`, and `kg_quality_checks`. KG schema v3 records exact upstream build IDs and frozen fact counts, and adds CalendarYear/Month/Quarter, entity FiscalYear, and cross-entity FiscalYearLabel dimensions.

The KG gate verifies build alignment, node counts, candidate exclusion, provenance status, edge endpoint existence and type, duplicate stable IDs, complete `DERIVED_FROM` inputs, source-definition provider edges, explicit ranking/screening scope, and that every TimePeriod has a calendar or fiscal hierarchy edge. A failed build stays inactive.

PostgreSQL serves indexed neighbor/fact/derived queries. JSONL remains an interchange format. `kg-retention` defaults to dry-run, preserves the active plus previous successful build, writes older builds to Parquet with ZSTD and SHA-256 manifests, verifies archive row counts/checksums, and only then permits PostgreSQL purge.
