SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS source_registry (
    source_id           TEXT PRIMARY KEY,
    source_name         TEXT NOT NULL,
    source_type         TEXT NOT NULL,
    authority_level     TEXT NOT NULL,
    market              TEXT,
    provider            TEXT,
    base_url            TEXT,
    access_method       TEXT,
    update_frequency    TEXT,
    license_note        TEXT,
    rate_limit_note     TEXT,
    is_active           INTEGER DEFAULT 1,
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ingestion_jobs (
    job_id              TEXT PRIMARY KEY,
    source_id           TEXT REFERENCES source_registry(source_id),
    job_type            TEXT,
    target_scope        TEXT,
    start_time          TEXT,
    end_time            TEXT,
    status              TEXT,
    records_found       INTEGER,
    records_saved       INTEGER,
    error_message       TEXT,
    config              TEXT
);

CREATE TABLE IF NOT EXISTS raw_objects (
    raw_object_id       TEXT PRIMARY KEY,
    source_id           TEXT REFERENCES source_registry(source_id),
    job_id              TEXT REFERENCES ingestion_jobs(job_id),
    object_type         TEXT,
    storage_uri         TEXT,
    original_url        TEXT,
    request_params      TEXT,
    response_headers    TEXT,
    response_status     INTEGER,
    content_sha256      TEXT,
    content_size_bytes  INTEGER,
    compression         TEXT,
    retrieval_time      TEXT,
    source_publish_date TEXT,
    source_update_time  TEXT,
    parse_status        TEXT DEFAULT 'unparsed',
    validation_status   TEXT DEFAULT 'unchecked',
    notes               TEXT
);

CREATE INDEX IF NOT EXISTS idx_raw_objects_source_id ON raw_objects(source_id);
CREATE INDEX IF NOT EXISTS idx_raw_objects_sha256 ON raw_objects(content_sha256);
CREATE INDEX IF NOT EXISTS idx_raw_objects_original_url ON raw_objects(original_url);

CREATE TABLE IF NOT EXISTS raw_records (
    raw_record_id       TEXT PRIMARY KEY,
    raw_object_id       TEXT REFERENCES raw_objects(raw_object_id),
    source_id           TEXT REFERENCES source_registry(source_id),
    record_key          TEXT,
    record_type         TEXT,
    record_json         TEXT,
    entity_hint         TEXT,
    metric_hint         TEXT,
    period_hint         TEXT,
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_raw_records_source_id ON raw_records(source_id);
CREATE INDEX IF NOT EXISTS idx_raw_records_record_key ON raw_records(record_key);

CREATE TABLE IF NOT EXISTS source_entities (
    source_entity_id    TEXT PRIMARY KEY,
    source_id           TEXT REFERENCES source_registry(source_id),
    source_code         TEXT,
    source_name         TEXT,
    aliases             TEXT,
    market              TEXT,
    raw_metadata        TEXT,
    first_seen_at       TEXT,
    last_seen_at        TEXT
);

CREATE TABLE IF NOT EXISTS metrics (
    metric_id           TEXT PRIMARY KEY,
    canonical_name      TEXT NOT NULL,
    metric_category     TEXT,
    statement_type      TEXT,
    period_type         TEXT,
    default_unit        TEXT,
    default_currency    TEXT,
    accounting_standard TEXT,
    aggregation_rule    TEXT,
    revision_risk       TEXT,
    ambiguity_notes     TEXT,
    build_id            TEXT,
    is_active           INTEGER DEFAULT 1,
    superseded_by       TEXT,
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at          TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_metrics_category ON metrics(metric_category);
CREATE INDEX IF NOT EXISTS idx_metrics_statement_type ON metrics(statement_type);

CREATE TABLE IF NOT EXISTS metric_alias_map (
    alias_id            TEXT PRIMARY KEY,
    metric_id           TEXT REFERENCES metrics(metric_id),
    source_id           TEXT REFERENCES source_registry(source_id),
    raw_field_name      TEXT,
    raw_concept_name    TEXT,
    confidence_score    REAL,
    build_id            TEXT,
    is_active           INTEGER DEFAULT 1,
    superseded_by       TEXT,
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_metric_alias_map_metric_id ON metric_alias_map(metric_id);
CREATE INDEX IF NOT EXISTS idx_metric_alias_map_source_concept ON metric_alias_map(source_id, raw_concept_name);
CREATE INDEX IF NOT EXISTS idx_metric_alias_map_raw_field ON metric_alias_map(raw_field_name);

CREATE TABLE IF NOT EXISTS canonical_entities (
    entity_id           TEXT PRIMARY KEY,
    canonical_name      TEXT NOT NULL,
    entity_type         TEXT NOT NULL,
    market              TEXT,
    country             TEXT,
    exchange            TEXT,
    ticker              TEXT,
    cik                 TEXT,
    isin                TEXT,
    currency            TEXT,
    fiscal_year_end     TEXT,
    industry            TEXT,
    build_id            TEXT,
    is_active           INTEGER DEFAULT 1,
    superseded_by       TEXT,
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at          TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_canonical_entities_type ON canonical_entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_canonical_entities_ticker ON canonical_entities(ticker);
CREATE INDEX IF NOT EXISTS idx_canonical_entities_cik ON canonical_entities(cik);

CREATE TABLE IF NOT EXISTS entity_alias_map (
    alias_id            TEXT PRIMARY KEY,
    entity_id           TEXT REFERENCES canonical_entities(entity_id),
    source_id           TEXT REFERENCES source_registry(source_id),
    source_code         TEXT,
    source_name         TEXT,
    alias               TEXT,
    confidence_score    REAL,
    build_id            TEXT,
    is_active           INTEGER DEFAULT 1,
    superseded_by       TEXT,
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_entity_alias_map_entity_id ON entity_alias_map(entity_id);
CREATE INDEX IF NOT EXISTS idx_entity_alias_map_source_code ON entity_alias_map(source_id, source_code);
CREATE INDEX IF NOT EXISTS idx_entity_alias_map_alias ON entity_alias_map(alias);

CREATE TABLE IF NOT EXISTS canonical_securities (
    security_id         TEXT PRIMARY KEY,
    company_entity_id  TEXT REFERENCES canonical_entities(entity_id),
    canonical_name     TEXT NOT NULL,
    security_type      TEXT,
    market             TEXT,
    country            TEXT,
    exchange           TEXT,
    ticker             TEXT,
    composite_ticker   TEXT,
    figi               TEXT,
    isin               TEXT,
    cusip              TEXT,
    currency           TEXT,
    is_primary_listing INTEGER DEFAULT 1,
    listing_status     TEXT,
    valid_from         TEXT,
    valid_to           TEXT,
    build_id           TEXT,
    is_active          INTEGER DEFAULT 1,
    superseded_by      TEXT,
    created_at         TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at         TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_canonical_securities_company ON canonical_securities(company_entity_id);
CREATE INDEX IF NOT EXISTS idx_canonical_securities_ticker_exchange ON canonical_securities(ticker, exchange);

CREATE TABLE IF NOT EXISTS entity_relationships (
    relationship_id    TEXT PRIMARY KEY,
    subject_entity_id  TEXT REFERENCES canonical_entities(entity_id),
    relationship_type  TEXT NOT NULL,
    object_id          TEXT,
    object_type        TEXT,
    object_entity_id   TEXT REFERENCES canonical_entities(entity_id),
    source_id          TEXT REFERENCES source_registry(source_id),
    source_code        TEXT,
    confidence_score   REAL,
    valid_from         TEXT,
    valid_to           TEXT,
    notes              TEXT,
    build_id           TEXT,
    is_active          INTEGER DEFAULT 1,
    superseded_by      TEXT,
    created_at         TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_entity_relationships_subject ON entity_relationships(subject_entity_id, relationship_type);
CREATE INDEX IF NOT EXISTS idx_entity_relationships_object ON entity_relationships(object_id, object_type);
CREATE INDEX IF NOT EXISTS idx_entity_relationships_object_entity ON entity_relationships(object_entity_id);

CREATE TABLE IF NOT EXISTS source_series_entity_map (
    series_map_id      TEXT PRIMARY KEY,
    source_id          TEXT REFERENCES source_registry(source_id),
    series_id          TEXT,
    series_entity_id   TEXT REFERENCES canonical_entities(entity_id),
    metric_id          TEXT REFERENCES metrics(metric_id),
    applies_to_entity_id TEXT REFERENCES canonical_entities(entity_id),
    instrument_entity_id TEXT REFERENCES canonical_entities(entity_id),
    frequency          TEXT,
    source_units       TEXT,
    seasonal_adjustment TEXT,
    notes              TEXT,
    build_id           TEXT,
    is_active          INTEGER DEFAULT 1,
    superseded_by      TEXT,
    created_at         TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_source_series_entity_map_source_series ON source_series_entity_map(source_id, series_id);
CREATE INDEX IF NOT EXISTS idx_source_series_entity_map_metric ON source_series_entity_map(metric_id);
CREATE INDEX IF NOT EXISTS idx_source_series_entity_map_target ON source_series_entity_map(applies_to_entity_id, instrument_entity_id);

CREATE TABLE IF NOT EXISTS standardized_facts (
    fact_id             TEXT PRIMARY KEY REFERENCES atomic_facts(fact_id),
    stable_fact_id      TEXT,
    build_id            TEXT,
    raw_snapshot_id     TEXT,
    is_active           INTEGER DEFAULT 1,
    superseded_by       TEXT,
    entity_id           TEXT REFERENCES canonical_entities(entity_id),
    metric_id           TEXT REFERENCES metrics(metric_id),
    normalized_value    REAL,
    normalized_unit     TEXT,
    normalized_currency TEXT,
    value_scale         TEXT,
    period_start        TEXT,
    period_end          TEXT,
    calendar_year       INTEGER,
    fiscal_year         INTEGER,
    fiscal_quarter      TEXT,
    time_basis          TEXT,
    metric_period_type  TEXT,
    source_definition_id TEXT REFERENCES source_metric_definitions(definition_id),
    frequency           TEXT,
    seasonal_adjustment TEXT,
    vintage_policy      TEXT,
    is_forecast         INTEGER,
    comparability_level TEXT,
    as_of_date          TEXT,
    report_date         TEXT,
    source_id           TEXT REFERENCES source_registry(source_id),
    raw_object_id       TEXT REFERENCES raw_objects(raw_object_id),
    verification_status TEXT,
    graph_ready          INTEGER DEFAULT 0,
    graph_ready_reason   TEXT,
    validation_flags    TEXT,
    conflict_group_id   TEXT,
    raw_equivalence_group_id TEXT,
    semantic_equivalence_group_id TEXT,
    confidence_score    REAL,
    notes               TEXT,
    updated_at          TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_standardized_facts_entity_metric ON standardized_facts(entity_id, metric_id);
CREATE INDEX IF NOT EXISTS idx_standardized_facts_period_end ON standardized_facts(period_end);
CREATE INDEX IF NOT EXISTS idx_standardized_facts_verification ON standardized_facts(verification_status);
CREATE INDEX IF NOT EXISTS idx_standardized_facts_graph_ready ON standardized_facts(graph_ready);
CREATE INDEX IF NOT EXISTS idx_standardized_facts_source_definition ON standardized_facts(source_definition_id);
CREATE INDEX IF NOT EXISTS idx_standardized_facts_comparability ON standardized_facts(comparability_level);
CREATE INDEX IF NOT EXISTS idx_standardized_facts_raw_equivalence ON standardized_facts(raw_equivalence_group_id);
CREATE INDEX IF NOT EXISTS idx_standardized_facts_semantic_equivalence ON standardized_facts(semantic_equivalence_group_id);

CREATE TABLE IF NOT EXISTS fact_quality_checks (
    check_id            TEXT PRIMARY KEY,
    fact_id             TEXT REFERENCES atomic_facts(fact_id),
    build_id            TEXT,
    is_active           INTEGER DEFAULT 1,
    superseded_by       TEXT,
    check_type          TEXT,
    status              TEXT,
    severity            TEXT,
    message             TEXT,
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_fact_quality_checks_fact_id ON fact_quality_checks(fact_id);
CREATE INDEX IF NOT EXISTS idx_fact_quality_checks_type_status ON fact_quality_checks(check_type, status);

CREATE TABLE IF NOT EXISTS derived_facts (
    derived_id          TEXT PRIMARY KEY,
    stable_derived_id   TEXT,
    build_id            TEXT,
    input_build_id      TEXT,
    is_active           INTEGER DEFAULT 1,
    superseded_by       TEXT,
    derived_type        TEXT,
    input_fact_ids      TEXT,
    entity_scope        TEXT,
    metric_scope        TEXT,
    time_scope          TEXT,
    scope_type          TEXT,
    scope_id            TEXT,
    scope_definition    TEXT,
    scope_entity_ids    TEXT,
    scope_source        TEXT,
    calculation_code    TEXT,
    output_value        REAL,
    output_table        TEXT,
    unit                TEXT,
    tolerance           REAL,
    verification_status TEXT,
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_derived_facts_type ON derived_facts(derived_type);
CREATE INDEX IF NOT EXISTS idx_derived_facts_status ON derived_facts(verification_status);

CREATE TABLE IF NOT EXISTS source_metric_definitions (
    definition_id       TEXT PRIMARY KEY,
    source_id           TEXT REFERENCES source_registry(source_id),
    metric_id           TEXT REFERENCES metrics(metric_id),
    raw_concept_name    TEXT,
    definition_text     TEXT,
    unit_rule           TEXT,
    frequency           TEXT,
    vintage_policy      TEXT,
    is_forecast         INTEGER,
    comparable_to_metric_id TEXT,
    comparability_level TEXT,
    notes               TEXT,
    build_id            TEXT,
    is_active           INTEGER DEFAULT 1,
    superseded_by       TEXT,
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_source_metric_definitions_source_metric ON source_metric_definitions(source_id, metric_id);
CREATE INDEX IF NOT EXISTS idx_source_metric_definitions_concept ON source_metric_definitions(raw_concept_name);

CREATE TABLE IF NOT EXISTS time_series_frequency_map (
    frequency_id        TEXT PRIMARY KEY,
    source_id           TEXT REFERENCES source_registry(source_id),
    metric_id           TEXT REFERENCES metrics(metric_id),
    series_id           TEXT,
    frequency           TEXT,
    seasonal_adjustment TEXT,
    period_type         TEXT,
    annualization_rule  TEXT,
    source_units        TEXT,
    notes               TEXT,
    build_id            TEXT,
    is_active           INTEGER DEFAULT 1,
    superseded_by       TEXT,
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_time_series_frequency_source_series ON time_series_frequency_map(source_id, series_id);
CREATE INDEX IF NOT EXISTS idx_time_series_frequency_metric ON time_series_frequency_map(metric_id);

CREATE TABLE IF NOT EXISTS document_text_chunks (
    chunk_id            TEXT PRIMARY KEY,
    stable_chunk_id     TEXT,
    build_id            TEXT,
    is_active           INTEGER DEFAULT 1,
    superseded_by       TEXT,
    raw_object_id       TEXT REFERENCES raw_objects(raw_object_id),
    source_id           TEXT REFERENCES source_registry(source_id),
    page_number         INTEGER,
    section_title       TEXT,
    text                TEXT,
    char_start          INTEGER,
    char_end            INTEGER,
    extraction_method   TEXT,
    confidence_score    REAL,
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_document_text_chunks_raw_object ON document_text_chunks(raw_object_id);
CREATE INDEX IF NOT EXISTS idx_document_text_chunks_source ON document_text_chunks(source_id);

CREATE TABLE IF NOT EXISTS raw_extracted_tables (
    table_id            TEXT PRIMARY KEY,
    stable_table_id     TEXT,
    build_id            TEXT,
    is_active           INTEGER DEFAULT 1,
    superseded_by       TEXT,
    raw_object_id       TEXT REFERENCES raw_objects(raw_object_id),
    source_id           TEXT REFERENCES source_registry(source_id),
    page_number         INTEGER,
    table_index         INTEGER,
    raw_table_json      TEXT,
    extraction_method   TEXT,
    confidence_score    REAL,
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_raw_extracted_tables_raw_object ON raw_extracted_tables(raw_object_id);

CREATE TABLE IF NOT EXISTS candidate_facts (
    candidate_id        TEXT PRIMARY KEY,
    stable_candidate_id TEXT,
    build_id            TEXT,
    is_active           INTEGER DEFAULT 1,
    superseded_by       TEXT,
    raw_object_id       TEXT REFERENCES raw_objects(raw_object_id),
    table_id            TEXT REFERENCES raw_extracted_tables(table_id),
    entity_id           TEXT REFERENCES canonical_entities(entity_id),
    metric_hint         TEXT,
    value               TEXT,
    unit                TEXT,
    period_hint         TEXT,
    evidence_text       TEXT,
    confidence_score    REAL,
    review_status      TEXT,
    candidate_state     TEXT,
    state_reason        TEXT,
    matched_metric_id   TEXT,
    evidence_status     TEXT,
    cross_check_status  TEXT,
    promotion_status    TEXT,
    promoted_fact_id    TEXT REFERENCES atomic_facts(fact_id),
    qa_eligible         INTEGER DEFAULT 0,
    kg_eligible         INTEGER DEFAULT 0,
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_candidate_facts_raw_object ON candidate_facts(raw_object_id);
CREATE INDEX IF NOT EXISTS idx_candidate_facts_review ON candidate_facts(review_status);
CREATE INDEX IF NOT EXISTS idx_candidate_facts_state ON candidate_facts(candidate_state, promotion_status);
CREATE INDEX IF NOT EXISTS idx_candidate_facts_eligibility ON candidate_facts(qa_eligible, kg_eligible);


CREATE TABLE IF NOT EXISTS source_documents (
    document_id         TEXT PRIMARY KEY,
    stable_document_id  TEXT,
    build_id            TEXT,
    is_active           INTEGER DEFAULT 1,
    superseded_by       TEXT,
    entity_id           TEXT REFERENCES canonical_entities(entity_id),
    source_id           TEXT REFERENCES source_registry(source_id),
    form_type           TEXT,
    report_type         TEXT,
    period_end          TEXT,
    filing_date         TEXT,
    storage_uri         TEXT,
    original_url        TEXT,
    raw_object_id       TEXT REFERENCES raw_objects(raw_object_id),
    document_status     TEXT,
    notes               TEXT,
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_source_documents_entity ON source_documents(entity_id);
CREATE INDEX IF NOT EXISTS idx_source_documents_source ON source_documents(source_id, form_type, report_type);
CREATE INDEX IF NOT EXISTS idx_source_documents_period ON source_documents(period_end, filing_date);
CREATE INDEX IF NOT EXISTS idx_source_documents_raw_object ON source_documents(raw_object_id);

CREATE TABLE IF NOT EXISTS atomic_facts (
    fact_id             TEXT PRIMARY KEY,
    stable_fact_id      TEXT,
    build_id            TEXT,
    raw_snapshot_id     TEXT,
    is_active           INTEGER DEFAULT 1,
    superseded_by       TEXT,
    entity_id           TEXT REFERENCES canonical_entities(entity_id),
    metric_id           TEXT REFERENCES metrics(metric_id),
    value               REAL,
    value_type          TEXT,
    unit                TEXT,
    currency            TEXT,
    period_start        TEXT,
    period_end          TEXT,
    fiscal_year         INTEGER,
    fiscal_quarter      TEXT,
    as_of_date          TEXT,
    report_date         TEXT,
    source_id           TEXT REFERENCES source_registry(source_id),
    raw_object_id       TEXT REFERENCES raw_objects(raw_object_id),
    source_field_name   TEXT,
    source_page_or_table TEXT,
    extraction_method   TEXT,
    confidence_score    REAL,
    verification_status TEXT,
    tolerance           REAL,
    notes               TEXT,
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_atomic_facts_entity_id ON atomic_facts(entity_id);
CREATE INDEX IF NOT EXISTS idx_atomic_facts_metric_id ON atomic_facts(metric_id);
CREATE INDEX IF NOT EXISTS idx_atomic_facts_period_end ON atomic_facts(period_end);
CREATE INDEX IF NOT EXISTS idx_atomic_facts_source ON atomic_facts(source_id, raw_object_id);
CREATE INDEX IF NOT EXISTS idx_atomic_facts_verification ON atomic_facts(verification_status);

CREATE TABLE IF NOT EXISTS data_coverage_report (
    source_id           TEXT PRIMARY KEY,
    entity_count        INTEGER,
    metric_count        INTEGER,
    min_date            TEXT,
    max_date            TEXT,
    object_count        INTEGER,
    missing_rate        REAL,
    parse_ready         INTEGER,
    quality_level       TEXT,
    updated_at          TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw_dataset_snapshots (
    snapshot_id         TEXT PRIMARY KEY,
    source_id           TEXT REFERENCES source_registry(source_id),
    snapshot_date       TEXT,
    storage_prefix      TEXT,
    object_count        INTEGER,
    total_size_bytes    INTEGER,
    manifest_uri        TEXT,
    checksum_uri        TEXT,
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pipeline_builds (
    build_id            TEXT PRIMARY KEY,
    layer               TEXT,
    command             TEXT,
    raw_snapshot_id     TEXT,
    input_build_id      TEXT,
    status              TEXT,
    started_at          TEXT,
    completed_at        TEXT,
    notes               TEXT
);

CREATE TABLE IF NOT EXISTS kg_builds (
    kg_build_id          TEXT PRIMARY KEY,
    graph_schema_version TEXT,
    input_fact_build_id  TEXT,
    input_qa_build_id    TEXT,
    input_entity_build_id TEXT,
    input_metric_build_id TEXT,
    input_source_definition_build_id TEXT,
    input_document_build_id TEXT,
    input_fact_count     INTEGER,
    input_derived_count  INTEGER,
    status               TEXT,
    started_at           TEXT,
    completed_at         TEXT,
    node_count           INTEGER,
    edge_count           INTEGER,
    quality_status       TEXT,
    notes                TEXT,
    is_active            INTEGER DEFAULT 1,
    superseded_by        TEXT
);
CREATE TABLE IF NOT EXISTS kg_nodes (
    node_id              TEXT PRIMARY KEY,
    stable_node_id       TEXT,
    kg_build_id          TEXT REFERENCES kg_builds(kg_build_id),
    node_type            TEXT NOT NULL,
    source_table         TEXT,
    source_pk            TEXT,
    properties_json      TEXT,
    is_active            INTEGER DEFAULT 1,
    superseded_by        TEXT,
    created_at           TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_kg_nodes_build_type ON kg_nodes(kg_build_id, node_type);
CREATE INDEX IF NOT EXISTS idx_kg_nodes_stable ON kg_nodes(stable_node_id);
CREATE TABLE IF NOT EXISTS kg_edges (
    edge_id              TEXT PRIMARY KEY,
    stable_edge_id       TEXT,
    kg_build_id          TEXT REFERENCES kg_builds(kg_build_id),
    src_node_id          TEXT NOT NULL,
    dst_node_id          TEXT NOT NULL,
    relation_type        TEXT NOT NULL,
    source_table         TEXT,
    source_pk            TEXT,
    properties_json      TEXT,
    is_active            INTEGER DEFAULT 1,
    superseded_by        TEXT,
    created_at           TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_kg_edges_build_type ON kg_edges(kg_build_id, relation_type);
CREATE INDEX IF NOT EXISTS idx_kg_edges_src ON kg_edges(src_node_id);
CREATE INDEX IF NOT EXISTS idx_kg_edges_dst ON kg_edges(dst_node_id);
CREATE INDEX IF NOT EXISTS idx_kg_edges_stable ON kg_edges(stable_edge_id);
CREATE TABLE IF NOT EXISTS kg_quality_checks (
    check_id             TEXT PRIMARY KEY,
    kg_build_id          TEXT REFERENCES kg_builds(kg_build_id),
    check_type           TEXT,
    status               TEXT,
    severity             TEXT,
    message              TEXT,
    created_at           TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_kg_quality_checks_build ON kg_quality_checks(kg_build_id, status, severity);
"""

SOURCE_REGISTRY_SEED = [
    {
        "source_id": "sec_companyfacts",
        "source_name": "SEC EDGAR Company Facts Bulk ZIP",
        "source_type": "bulk_zip",
        "authority_level": "S1_official",
        "market": "US",
        "provider": "SEC",
        "base_url": "https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip",
        "access_method": "download",
        "update_frequency": "daily",
        "license_note": "Official SEC public data. Respect SEC fair access policy.",
        "rate_limit_note": "Set a descriptive User-Agent; avoid abusive request rates."
    },
    {
        "source_id": "sec_submissions",
        "source_name": "SEC EDGAR Submissions Bulk ZIP",
        "source_type": "bulk_zip",
        "authority_level": "S1_official",
        "market": "US",
        "provider": "SEC",
        "base_url": "https://www.sec.gov/Archives/edgar/daily-index/xbrl/submissions.zip",
        "access_method": "download",
        "update_frequency": "daily",
        "license_note": "Official SEC public data. Respect SEC fair access policy.",
        "rate_limit_note": "Set a descriptive User-Agent; avoid abusive request rates."
    },
    {
        "source_id": "sec_filings",
        "source_name": "SEC EDGAR Filing Primary Documents",
        "source_type": "html_xbrl_txt",
        "authority_level": "S1_official",
        "market": "US",
        "provider": "SEC",
        "base_url": "https://www.sec.gov/Archives/edgar/data",
        "access_method": "REST_download",
        "update_frequency": "real_time_daily",
        "license_note": "Official SEC public filing documents. Respect SEC fair access policy.",
        "rate_limit_note": "Set a descriptive User-Agent; avoid abusive request rates."
    },
    {
        "source_id": "fred_observations",
        "source_name": "FRED Series Observations",
        "source_type": "api",
        "authority_level": "S2_database",
        "market": "US_Global",
        "provider": "FRED",
        "base_url": "https://api.stlouisfed.org/fred",
        "access_method": "REST",
        "update_frequency": "varies_by_series",
        "license_note": "FRED API terms apply.",
        "rate_limit_note": "Requires API key for production use."
    },
    {
        "source_id": "worldbank_indicators",
        "source_name": "World Bank Indicators API",
        "source_type": "api",
        "authority_level": "S1_official",
        "market": "Global",
        "provider": "WorldBank",
        "base_url": "https://api.worldbank.org/v2",
        "access_method": "REST",
        "update_frequency": "annual_monthly_quarterly",
        "license_note": "World Bank data terms apply.",
        "rate_limit_note": "Use pagination and retry politely."
    },
    {
        "source_id": "imf_sdmx",
        "source_name": "IMF SDMX API",
        "source_type": "api",
        "authority_level": "S1_official",
        "market": "Global",
        "provider": "IMF",
        "base_url": "https://data.imf.org",
        "access_method": "SDMX",
        "update_frequency": "varies_by_dataset",
        "license_note": "IMF data terms apply.",
        "rate_limit_note": "Connector reserved for Phase 3."
    },
    {
        "source_id": "cninfo_announcements",
        "source_name": "CNInfo Announcements and Reports",
        "source_type": "pdf",
        "authority_level": "S1_official",
        "market": "CN",
        "provider": "CNInfo",
        "base_url": "https://www.cninfo.com.cn",
        "access_method": "crawl",
        "update_frequency": "real_time_daily",
        "license_note": "CNInfo terms apply.",
        "rate_limit_note": "Connector reserved for Phase 2."
    }
]

