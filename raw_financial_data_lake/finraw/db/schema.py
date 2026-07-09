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
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_entity_alias_map_entity_id ON entity_alias_map(entity_id);
CREATE INDEX IF NOT EXISTS idx_entity_alias_map_source_code ON entity_alias_map(source_id, source_code);
CREATE INDEX IF NOT EXISTS idx_entity_alias_map_alias ON entity_alias_map(alias);

CREATE TABLE IF NOT EXISTS standardized_facts (
    fact_id             TEXT PRIMARY KEY REFERENCES atomic_facts(fact_id),
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
    as_of_date          TEXT,
    report_date         TEXT,
    source_id           TEXT REFERENCES source_registry(source_id),
    raw_object_id       TEXT REFERENCES raw_objects(raw_object_id),
    verification_status TEXT,
    validation_flags    TEXT,
    conflict_group_id   TEXT,
    confidence_score    REAL,
    notes               TEXT,
    updated_at          TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_standardized_facts_entity_metric ON standardized_facts(entity_id, metric_id);
CREATE INDEX IF NOT EXISTS idx_standardized_facts_period_end ON standardized_facts(period_end);
CREATE INDEX IF NOT EXISTS idx_standardized_facts_verification ON standardized_facts(verification_status);

CREATE TABLE IF NOT EXISTS fact_quality_checks (
    check_id            TEXT PRIMARY KEY,
    fact_id             TEXT REFERENCES atomic_facts(fact_id),
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
    derived_type        TEXT,
    input_fact_ids      TEXT,
    entity_scope        TEXT,
    metric_scope        TEXT,
    time_scope          TEXT,
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
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_time_series_frequency_source_series ON time_series_frequency_map(source_id, series_id);
CREATE INDEX IF NOT EXISTS idx_time_series_frequency_metric ON time_series_frequency_map(metric_id);

CREATE TABLE IF NOT EXISTS document_text_chunks (
    chunk_id            TEXT PRIMARY KEY,
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
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_candidate_facts_raw_object ON candidate_facts(raw_object_id);
CREATE INDEX IF NOT EXISTS idx_candidate_facts_review ON candidate_facts(review_status);

CREATE TABLE IF NOT EXISTS atomic_facts (
    fact_id             TEXT PRIMARY KEY,
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

