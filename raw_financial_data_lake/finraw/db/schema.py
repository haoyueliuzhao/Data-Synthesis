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
    entity_scope_id     TEXT,
    financial_scope_type TEXT,
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
CREATE INDEX IF NOT EXISTS idx_standardized_facts_financial_scope ON standardized_facts(entity_scope_id, financial_scope_type);
CREATE INDEX IF NOT EXISTS idx_standardized_facts_period_end ON standardized_facts(period_end);
CREATE INDEX IF NOT EXISTS idx_standardized_facts_verification ON standardized_facts(verification_status);
CREATE INDEX IF NOT EXISTS idx_standardized_facts_graph_ready ON standardized_facts(graph_ready);
CREATE INDEX IF NOT EXISTS idx_standardized_facts_source_definition ON standardized_facts(source_definition_id);
CREATE INDEX IF NOT EXISTS idx_standardized_facts_comparability ON standardized_facts(comparability_level);
CREATE INDEX IF NOT EXISTS idx_standardized_facts_raw_equivalence ON standardized_facts(raw_equivalence_group_id);
CREATE INDEX IF NOT EXISTS idx_standardized_facts_semantic_equivalence ON standardized_facts(semantic_equivalence_group_id);
CREATE INDEX IF NOT EXISTS idx_standardized_facts_qa_series ON standardized_facts(build_id, metric_id, entity_id, fiscal_year, fiscal_quarter, period_end);

CREATE TABLE IF NOT EXISTS fact_universe_builds (
    universe_build_id   TEXT PRIMARY KEY,
    input_fact_build_id TEXT NOT NULL,
    input_entity_build_id TEXT NOT NULL,
    policy_id           TEXT NOT NULL,
    policy_version      TEXT NOT NULL,
    config_hash         TEXT NOT NULL,
    membership_manifest_hash TEXT,
    target_greater_china_share REAL NOT NULL,
    actual_greater_china_share REAL,
    candidate_fact_count INTEGER DEFAULT 0,
    member_count        INTEGER DEFAULT 0,
    greater_china_member_count INTEGER DEFAULT 0,
    international_member_count INTEGER DEFAULT 0,
    unclassified_candidate_count INTEGER DEFAULT 0,
    status              TEXT NOT NULL,
    quality_status      TEXT,
    started_at          TEXT,
    completed_at        TEXT,
    is_active           INTEGER DEFAULT 0,
    superseded_by       TEXT,
    notes               TEXT
);

CREATE INDEX IF NOT EXISTS idx_fact_universe_builds_active
ON fact_universe_builds(is_active, status, input_fact_build_id);

CREATE TABLE IF NOT EXISTS fact_universe_members (
    membership_id       TEXT PRIMARY KEY,
    universe_build_id   TEXT NOT NULL REFERENCES fact_universe_builds(universe_build_id),
    fact_id             TEXT NOT NULL REFERENCES standardized_facts(fact_id),
    region_bucket       TEXT NOT NULL,
    stratum_key         TEXT NOT NULL,
    selection_rank      INTEGER NOT NULL,
    selection_reason    TEXT NOT NULL,
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_fact_universe_members_unique
ON fact_universe_members(universe_build_id, fact_id);
CREATE INDEX IF NOT EXISTS idx_fact_universe_members_fact
ON fact_universe_members(fact_id, universe_build_id);
CREATE INDEX IF NOT EXISTS idx_fact_universe_members_region
ON fact_universe_members(universe_build_id, region_bucket);


CREATE TABLE IF NOT EXISTS fact_universe_derived_members (
    membership_id       TEXT PRIMARY KEY,
    universe_build_id   TEXT NOT NULL REFERENCES fact_universe_builds(universe_build_id),
    derived_id          TEXT NOT NULL REFERENCES derived_facts(derived_id),
    region_bucket       TEXT NOT NULL,
    stratum_key         TEXT NOT NULL,
    selection_rank      INTEGER NOT NULL,
    selection_reason    TEXT NOT NULL,
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_fact_universe_derived_unique
ON fact_universe_derived_members(universe_build_id, derived_id);
CREATE INDEX IF NOT EXISTS idx_fact_universe_derived_id
ON fact_universe_derived_members(derived_id, universe_build_id);
CREATE INDEX IF NOT EXISTS idx_fact_universe_derived_region
ON fact_universe_derived_members(universe_build_id, region_bucket);

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
    period_start        TEXT,
    period_end          TEXT,
    fiscal_year         INTEGER,
    fiscal_quarter      TEXT,
    currency            TEXT,
    value_scale         TEXT,
    source_field_name   TEXT,
    statement_type      TEXT,
    financial_scope_type TEXT,
    page_number         INTEGER,
    row_index           INTEGER,
    column_index        INTEGER,
    extraction_metadata TEXT,
    evidence_sha256     TEXT,
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
CREATE INDEX IF NOT EXISTS idx_candidate_facts_source_metric_period
ON candidate_facts(matched_metric_id, entity_id, period_end);

CREATE TABLE IF NOT EXISTS candidate_fact_evidence (
    evidence_id         TEXT PRIMARY KEY,
    candidate_id        TEXT REFERENCES candidate_facts(candidate_id),
    build_id            TEXT,
    raw_object_id       TEXT REFERENCES raw_objects(raw_object_id),
    table_id            TEXT REFERENCES raw_extracted_tables(table_id),
    page_number         INTEGER,
    unit_source_page    INTEGER,
    unit_evidence_text  TEXT,
    statement_source_page INTEGER,
    period_source_page  INTEGER,
    statement_type      TEXT,
    financial_scope_type TEXT,
    row_index           INTEGER,
    column_index        INTEGER,
    source_field_name   TEXT,
    raw_value_text      TEXT,
    period_label        TEXT,
    evidence_text       TEXT,
    evidence_sha256     TEXT,
    verification_method TEXT,
    validation_status   TEXT,
    validation_errors   TEXT,
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_candidate_fact_evidence_candidate ON candidate_fact_evidence(candidate_id);
CREATE INDEX IF NOT EXISTS idx_candidate_fact_evidence_object_page ON candidate_fact_evidence(raw_object_id, page_number);


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
    input_fact_universe_build_id TEXT,
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
CREATE INDEX IF NOT EXISTS idx_kg_nodes_build_type_node ON kg_nodes(kg_build_id, node_type, node_id);
CREATE INDEX IF NOT EXISTS idx_kg_nodes_build_type_table_node ON kg_nodes(kg_build_id, node_type, source_table, node_id);
CREATE INDEX IF NOT EXISTS idx_kg_nodes_build_type_source ON kg_nodes(kg_build_id, node_type, source_pk);
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
CREATE TABLE IF NOT EXISTS kg_archives (
    archive_id          TEXT PRIMARY KEY,
    kg_build_id         TEXT NOT NULL REFERENCES kg_builds(kg_build_id),
    archive_uri         TEXT NOT NULL,
    archive_format      TEXT NOT NULL,
    compression         TEXT,
    node_count          INTEGER,
    edge_count          INTEGER,
    quality_check_count INTEGER,
    node_sha256         TEXT,
    edge_sha256         TEXT,
    quality_sha256      TEXT,
    manifest_sha256     TEXT,
    status              TEXT NOT NULL,
    created_at          TEXT,
    verified_at         TEXT,
    purged_at           TEXT,
    notes               TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_kg_archives_build ON kg_archives(kg_build_id);
CREATE INDEX IF NOT EXISTS idx_kg_archives_status ON kg_archives(status, created_at);
-- Layer 5: deterministic QA build
CREATE TABLE IF NOT EXISTS qa_builds (
            qa_build_id TEXT PRIMARY KEY,
            kg_build_id TEXT NOT NULL,
            graph_schema_version TEXT NOT NULL,
            fact_build_id TEXT,
            derived_build_id TEXT,
            entity_build_id TEXT,
            metric_build_id TEXT,
            source_definition_build_id TEXT,
            document_build_id TEXT,
            config_hash TEXT,
            template_manifest_hash TEXT,
            question_parser_version TEXT,
            question_parser_manifest_hash TEXT,
            pattern_manifest_hash TEXT,
            operator_manifest_hash TEXT,
            difficulty_policy_hash TEXT,
            generator_version TEXT,
            git_commit_sha TEXT,
            split_policy_hash TEXT,
            status TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            candidate_count BIGINT DEFAULT 0,
            passed_count BIGINT DEFAULT 0,
            sample_count BIGINT DEFAULT 0,
            quality_status TEXT,
            is_active INTEGER DEFAULT 0,
            superseded_by TEXT,
            notes TEXT
        );
CREATE TABLE IF NOT EXISTS qa_templates (
            template_id TEXT PRIMARY KEY,
            task_family TEXT NOT NULL,
            source_type TEXT,
            entity_type TEXT,
            metric_category TEXT,
            period_type TEXT,
            language TEXT NOT NULL,
            template_text TEXT NOT NULL,
            required_slots TEXT NOT NULL,
            answer_type TEXT NOT NULL,
            difficulty_base TEXT NOT NULL,
            is_active INTEGER DEFAULT 1
        );
CREATE TABLE IF NOT EXISTS qa_graph_patterns (
            pattern_key TEXT PRIMARY KEY,
            pattern_id TEXT NOT NULL,
            pattern_version INTEGER NOT NULL,
            pattern_family TEXT NOT NULL,
            matcher TEXT,
            pattern_hash TEXT NOT NULL,
            node_constraints TEXT NOT NULL,
            edge_constraints TEXT NOT NULL,
            semantic_constraints TEXT NOT NULL,
            operator_template TEXT NOT NULL,
            answer_schema TEXT NOT NULL,
            difficulty_base TEXT NOT NULL,
            question_intents TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            UNIQUE(pattern_id, pattern_version)
        );
CREATE TABLE IF NOT EXISTS qa_candidates (
            candidate_id TEXT PRIMARY KEY,
            stable_candidate_id TEXT NOT NULL,
            qa_build_id TEXT NOT NULL,
            task_family TEXT NOT NULL,
            task_subtype TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            pattern_id TEXT,
            pattern_version INTEGER,
            pattern_hash TEXT,
            operation_plan_id TEXT,
            operation_plan_hash TEXT,
            graph_features TEXT,
            difficulty_score REAL,
            answer_schema TEXT,
            question_intent TEXT,
            entity_ids TEXT NOT NULL,
            metric_ids TEXT NOT NULL,
            time_scope TEXT NOT NULL,
            entity_scope TEXT NOT NULL,
            source_fact_ids TEXT NOT NULL,
            source_derived_ids TEXT NOT NULL,
            source_document_ids TEXT NOT NULL,
            raw_object_ids TEXT NOT NULL,
            canonical_semantics TEXT NOT NULL,
            derived_payload TEXT NOT NULL,
            recomputed_payload TEXT NOT NULL,
            answer_payload TEXT NOT NULL,
            kg_path TEXT NOT NULL,
            eligibility_status TEXT NOT NULL,
            rejection_reasons TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
CREATE TABLE IF NOT EXISTS qa_operation_plans (
            plan_id TEXT PRIMARY KEY,
            qa_build_id TEXT NOT NULL,
            candidate_id TEXT NOT NULL,
            pattern_id TEXT NOT NULL,
            pattern_version INTEGER NOT NULL,
            operator_dag TEXT NOT NULL,
            input_bindings TEXT NOT NULL,
            intermediate_results TEXT NOT NULL,
            output_schema TEXT NOT NULL,
            recompute_status TEXT NOT NULL,
            validation_errors TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
CREATE TABLE IF NOT EXISTS qa_samples (
            qa_id TEXT PRIMARY KEY,
            stable_qa_id TEXT NOT NULL,
            qa_group_id TEXT NOT NULL,
            semantic_cluster_id TEXT NOT NULL,
            qa_build_id TEXT NOT NULL,
            candidate_id TEXT NOT NULL,
            template_id TEXT,
            template_hash TEXT,
            surface_form_id TEXT,
            paraphrase_group_id TEXT,
            linguistic_style TEXT,
            graph_pattern_id TEXT,
            operation_depth INTEGER,
            task_family TEXT NOT NULL,
            task_subtype TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            language TEXT NOT NULL,
            question TEXT NOT NULL,
            canonical_question TEXT NOT NULL,
            answer_type TEXT NOT NULL,
            answer_value TEXT NOT NULL,
            answer_text TEXT NOT NULL,
            unit TEXT,
            currency TEXT,
            rubric TEXT NOT NULL,
            source_metadata TEXT NOT NULL,
            generation_method TEXT NOT NULL,
            validation_status TEXT NOT NULL,
            split TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
CREATE TABLE IF NOT EXISTS qa_distribution_labels (
            alignment_id TEXT PRIMARY KEY,
            qa_id TEXT NOT NULL,
            qa_build_id TEXT NOT NULL,
            alignment_standard TEXT NOT NULL,
            alignment_version TEXT NOT NULL,
            benchmark_task TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            market_subset TEXT NOT NULL,
            language TEXT NOT NULL,
            topic TEXT NOT NULL,
            subtopic TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            metric_families TEXT NOT NULL,
            source_classes TEXT NOT NULL,
            time_basis TEXT NOT NULL,
            frequency TEXT NOT NULL,
            period_count INTEGER NOT NULL,
            time_span_months INTEGER NOT NULL,
            answer_type TEXT NOT NULL,
            operation_families TEXT NOT NULL,
            primary_operation_family TEXT NOT NULL,
            operation_depth INTEGER NOT NULL,
            scope_size INTEGER NOT NULL,
            rubric_type TEXT NOT NULL,
            generation_pipeline TEXT NOT NULL,
            structural_features TEXT NOT NULL,
            completeness_checks TEXT NOT NULL,
            classification_reasons TEXT NOT NULL,
            label_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(qa_id, alignment_standard, alignment_version)
        );
CREATE INDEX IF NOT EXISTS idx_qa_distribution_build_task ON qa_distribution_labels(qa_build_id, benchmark_task, market_subset);
CREATE INDEX IF NOT EXISTS idx_qa_distribution_build_task_difficulty ON qa_distribution_labels(qa_build_id, benchmark_task, difficulty);
CREATE TABLE IF NOT EXISTS qa_evidence_paths (
            path_id TEXT PRIMARY KEY,
            qa_id TEXT NOT NULL,
            path_type TEXT NOT NULL,
            ordered_node_ids TEXT NOT NULL,
            ordered_edge_ids TEXT NOT NULL,
            evidence_node_ids TEXT NOT NULL,
            evidence_edges TEXT NOT NULL,
            evidence_components TEXT NOT NULL,
            source_fact_ids TEXT NOT NULL,
            source_derived_ids TEXT NOT NULL,
            raw_object_ids TEXT NOT NULL,
            source_document_ids TEXT NOT NULL
        );
CREATE TABLE IF NOT EXISTS qa_quality_checks (
            check_id TEXT PRIMARY KEY,
            qa_id TEXT NOT NULL,
            qa_build_id TEXT NOT NULL,
            check_name TEXT NOT NULL,
            check_status TEXT NOT NULL,
            observed_value TEXT,
            expected_value TEXT,
            message TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
CREATE TABLE IF NOT EXISTS qa_evaluation_runs (
            evaluation_run_id TEXT PRIMARY KEY,
            qa_build_id TEXT NOT NULL,
            rubric_version TEXT NOT NULL,
            rubric_hash TEXT NOT NULL,
            evaluation_config_hash TEXT NOT NULL,
            judge_config_hash TEXT NOT NULL,
            judge_manifest TEXT NOT NULL,
            sample_manifest TEXT NOT NULL,
            sample_manifest_hash TEXT NOT NULL,
            calibration_version TEXT,
            evaluation_mode TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            git_commit_sha TEXT,
            notes TEXT NOT NULL
        );
CREATE TABLE IF NOT EXISTS qa_judge_calls (
            judge_call_id TEXT PRIMARY KEY,
            evaluation_run_id TEXT NOT NULL,
            qa_id TEXT NOT NULL,
            judge_role TEXT NOT NULL,
            provider TEXT,
            requested_model TEXT,
            response_model TEXT,
            prompt_hash TEXT,
            response_hash TEXT,
            input_view_hash TEXT NOT NULL,
            scores TEXT NOT NULL,
            reviewed_dimensions TEXT NOT NULL,
            resolutions TEXT NOT NULL,
            fatal_flags TEXT NOT NULL,
            issue_codes TEXT NOT NULL,
            confidence REAL,
            escalate_to_human INTEGER DEFAULT 0,
            brief_justification TEXT NOT NULL,
            telemetry TEXT NOT NULL,
            status TEXT NOT NULL,
            error_message TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(evaluation_run_id, qa_id, judge_role)
        );
CREATE TABLE IF NOT EXISTS qa_evaluation_items (
            evaluation_item_id TEXT PRIMARY KEY,
            evaluation_run_id TEXT NOT NULL,
            qa_id TEXT NOT NULL,
            deterministic_gate_status TEXT NOT NULL,
            deterministic_gate_reasons TEXT NOT NULL,
            dimension_scores TEXT NOT NULL,
            subjective_quality_score REAL,
            standalone_financial_value_score REAL,
            dataset_role_value_score REAL NOT NULL,
            coverage_contributions TEXT NOT NULL,
            dataset_role_components TEXT NOT NULL,
            judge_disagreement TEXT NOT NULL,
            judge_confidence REAL,
            fatal_flags TEXT NOT NULL,
            confirmed_fatal_flags TEXT NOT NULL,
            issue_codes TEXT NOT NULL,
            decision TEXT NOT NULL,
            decision_reasons TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(evaluation_run_id, qa_id)
        );
CREATE TABLE IF NOT EXISTS qa_human_reviews (
            human_review_id TEXT PRIMARY KEY,
            evaluation_run_id TEXT NOT NULL,
            qa_id TEXT NOT NULL,
            reviewer_id TEXT NOT NULL,
            rubric_version TEXT NOT NULL,
            dimension_scores TEXT NOT NULL,
            fatal_flags TEXT NOT NULL,
            decision TEXT NOT NULL,
            reason_codes TEXT NOT NULL,
            reviewed_at TEXT NOT NULL,
            UNIQUE(evaluation_run_id, qa_id, reviewer_id)
        );
CREATE TABLE IF NOT EXISTS qa_perturbation_cases (
            perturbation_id TEXT PRIMARY KEY,
            source_qa_id TEXT NOT NULL,
            perturbed_question TEXT NOT NULL,
            perturbation_type TEXT NOT NULL,
            expected_affected_dimensions TEXT NOT NULL,
            expected_fatal_flags TEXT NOT NULL,
            mutation_manifest TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
CREATE TABLE IF NOT EXISTS qa_quality_releases (
            quality_release_id TEXT PRIMARY KEY,
            qa_build_id TEXT NOT NULL,
            evaluation_run_id TEXT NOT NULL,
            selection_policy_version TEXT NOT NULL,
            target_size BIGINT NOT NULL,
            distribution_contract TEXT NOT NULL,
            quality_thresholds TEXT NOT NULL,
            member_manifest_hash TEXT,
            status TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
CREATE TABLE IF NOT EXISTS qa_quality_release_members (
            release_member_id TEXT PRIMARY KEY,
            quality_release_id TEXT NOT NULL,
            qa_id TEXT NOT NULL,
            selection_score REAL NOT NULL,
            subjective_score REAL NOT NULL,
            dataset_role_score REAL NOT NULL,
            novelty_score REAL NOT NULL,
            selection_stratum TEXT NOT NULL,
            selection_reason TEXT NOT NULL,
            is_selected INTEGER DEFAULT 0,
            UNIQUE(quality_release_id, qa_id)
        );
CREATE TABLE IF NOT EXISTS qa_empirical_runs (
            empirical_run_id TEXT PRIMARY KEY,
            qa_build_ids TEXT NOT NULL,
            evaluation_mode TEXT NOT NULL,
            model_manifest TEXT NOT NULL,
            sample_manifest TEXT NOT NULL,
            config_hash TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            notes TEXT NOT NULL
        );
CREATE TABLE IF NOT EXISTS qa_empirical_model_trials (
            trial_id TEXT PRIMARY KEY,
            empirical_run_id TEXT NOT NULL,
            qa_build_id TEXT NOT NULL,
            qa_id TEXT NOT NULL,
            model_role TEXT NOT NULL,
            provider TEXT,
            requested_model TEXT NOT NULL,
            response_model TEXT,
            trial_mode TEXT NOT NULL,
            selected_evidence_ids TEXT NOT NULL,
            tool_trace TEXT NOT NULL,
            answer_text TEXT NOT NULL,
            answer_payload TEXT NOT NULL,
            match_status TEXT NOT NULL,
            match_details TEXT NOT NULL,
            api_call_success INTEGER NOT NULL,
            json_contract_success INTEGER NOT NULL,
            semantic_answer_correct INTEGER NOT NULL,
            unit_currency_correct INTEGER NOT NULL,
            row_completeness INTEGER NOT NULL,
            order_correct INTEGER NOT NULL,
            evidence_selection_correct INTEGER,
            end_to_end_correct INTEGER NOT NULL,
            prompt_hash TEXT NOT NULL,
            response_hash TEXT,
            telemetry TEXT NOT NULL,
            status TEXT NOT NULL,
            error_message TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(empirical_run_id, qa_id, model_role)
        );
CREATE INDEX IF NOT EXISTS idx_qaempirical_runs_status ON qa_empirical_runs(status, started_at);
CREATE INDEX IF NOT EXISTS idx_qaempirical_trials_run_model ON qa_empirical_model_trials(empirical_run_id, model_role, match_status);
CREATE INDEX IF NOT EXISTS idx_qaeval_runs_build_status ON qa_evaluation_runs(qa_build_id, status);
CREATE INDEX IF NOT EXISTS idx_qaeval_calls_run_qa ON qa_judge_calls(evaluation_run_id, qa_id, status);
CREATE INDEX IF NOT EXISTS idx_qaeval_items_run_decision ON qa_evaluation_items(evaluation_run_id, decision);
CREATE INDEX IF NOT EXISTS idx_qaeval_reviews_run_qa ON qa_human_reviews(evaluation_run_id, qa_id);
CREATE INDEX IF NOT EXISTS idx_qaeval_release_run ON qa_quality_releases(evaluation_run_id, status);
CREATE TABLE IF NOT EXISTS qa_archives (
    archive_id          TEXT PRIMARY KEY,
    qa_build_id         TEXT NOT NULL REFERENCES qa_builds(qa_build_id),
    archive_uri         TEXT NOT NULL,
    archive_format      TEXT NOT NULL,
    compression         TEXT,
    candidate_count     BIGINT,
    sample_count        BIGINT,
    evidence_count      BIGINT,
    quality_check_count BIGINT,
    manifest_sha256     TEXT,
    status              TEXT NOT NULL,
    created_at          TEXT,
    verified_at         TEXT,
    purged_at           TEXT,
    notes               TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_qa_archives_build ON qa_archives(qa_build_id);
CREATE INDEX IF NOT EXISTS idx_qa_archives_status ON qa_archives(status, created_at);
CREATE INDEX IF NOT EXISTS idx_kg_edges_build_rel_src ON kg_edges(kg_build_id, relation_type, src_node_id);
CREATE INDEX IF NOT EXISTS idx_kg_edges_build_rel_dst ON kg_edges(kg_build_id, relation_type, dst_node_id);
CREATE INDEX IF NOT EXISTS idx_qa_builds_kg_status ON qa_builds(kg_build_id, status);
CREATE INDEX IF NOT EXISTS idx_qa_candidates_task_status ON qa_candidates(qa_build_id, task_subtype, eligibility_status);
CREATE INDEX IF NOT EXISTS idx_qa_candidates_stable ON qa_candidates(stable_candidate_id);
CREATE INDEX IF NOT EXISTS idx_qa_samples_build_status ON qa_samples(qa_build_id, validation_status);
CREATE INDEX IF NOT EXISTS idx_qa_samples_group_split ON qa_samples(qa_group_id, split);
CREATE INDEX IF NOT EXISTS idx_qa_samples_cluster ON qa_samples(semantic_cluster_id);
CREATE INDEX IF NOT EXISTS idx_qa_evidence_qa ON qa_evidence_paths(qa_id);
CREATE INDEX IF NOT EXISTS idx_qa_quality_build_status ON qa_quality_checks(qa_build_id, check_status);
CREATE INDEX IF NOT EXISTS idx_qa_patterns_family_active ON qa_graph_patterns(pattern_family, is_active);
CREATE INDEX IF NOT EXISTS idx_qa_candidates_pattern ON qa_candidates(qa_build_id, pattern_id, eligibility_status);
CREATE INDEX IF NOT EXISTS idx_qa_plans_build_pattern ON qa_operation_plans(qa_build_id, pattern_id, recompute_status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_qa_plans_candidate ON qa_operation_plans(candidate_id);

-- Semi-open Financial Analysis Compiler
CREATE TABLE IF NOT EXISTS analysis_builds (
            analysis_build_id TEXT PRIMARY KEY,
            kg_build_id TEXT NOT NULL,
            graph_schema_version TEXT NOT NULL,
            fact_build_id TEXT NOT NULL,
            entity_build_id TEXT NOT NULL,
            metric_build_id TEXT NOT NULL,
            signal_registry_manifest_hash TEXT NOT NULL,
            analysis_pattern_manifest_hash TEXT NOT NULL,
            claim_schema_manifest_hash TEXT NOT NULL,
            conclusion_policy_manifest_hash TEXT NOT NULL,
            analysis_verifier_manifest_hash TEXT NOT NULL,
            config_hash TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            candidate_count BIGINT DEFAULT 0,
            signal_count BIGINT DEFAULT 0,
            sample_count BIGINT DEFAULT 0,
            passed_count BIGINT DEFAULT 0,
            quality_status TEXT,
            is_active INTEGER DEFAULT 0,
            superseded_by TEXT,
            notes TEXT NOT NULL
        );
CREATE TABLE IF NOT EXISTS financial_signal_specs (
            signal_spec_id TEXT PRIMARY KEY,
            signal_type TEXT NOT NULL,
            signal_version INTEGER NOT NULL,
            signal_category TEXT NOT NULL,
            input_roles TEXT NOT NULL,
            required_metrics TEXT NOT NULL,
            required_periods INTEGER NOT NULL,
            required_scope TEXT NOT NULL,
            semantic_constraints TEXT NOT NULL,
            operator_dag TEXT NOT NULL,
            output_schema TEXT NOT NULL,
            direction_policy TEXT NOT NULL,
            strength_policy TEXT NOT NULL,
            caveat_policy TEXT NOT NULL,
            signal_hash TEXT NOT NULL,
            is_active INTEGER DEFAULT 1
        );
CREATE TABLE IF NOT EXISTS financial_signal_instances (
            signal_id TEXT PRIMARY KEY,
            signal_spec_id TEXT NOT NULL,
            analysis_build_id TEXT NOT NULL,
            entity_ids TEXT NOT NULL,
            metric_ids TEXT NOT NULL,
            period_scope TEXT NOT NULL,
            scope_definition TEXT,
            input_fact_ids TEXT NOT NULL,
            input_derived_ids TEXT NOT NULL,
            operator_plan TEXT NOT NULL,
            intermediate_results TEXT NOT NULL,
            signal_payload TEXT NOT NULL,
            direction TEXT NOT NULL,
            strength TEXT NOT NULL,
            confidence REAL NOT NULL,
            supporting_evidence_ids TEXT NOT NULL,
            counter_evidence_ids TEXT NOT NULL,
            recompute_status TEXT NOT NULL,
            signal_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
CREATE TABLE IF NOT EXISTS analysis_patterns (
            pattern_key TEXT PRIMARY KEY,
            analysis_pattern_id TEXT NOT NULL,
            pattern_version INTEGER NOT NULL,
            analysis_family TEXT NOT NULL,
            question_intents TEXT NOT NULL,
            required_signal_roles TEXT NOT NULL,
            optional_signal_roles TEXT NOT NULL,
            counter_signal_roles TEXT NOT NULL,
            evidence_constraints TEXT NOT NULL,
            claim_schema TEXT NOT NULL,
            conclusion_policy TEXT NOT NULL,
            forbidden_claim_types TEXT NOT NULL,
            difficulty_base TEXT NOT NULL,
            instruction_template TEXT NOT NULL,
            pattern_hash TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            UNIQUE(analysis_pattern_id, pattern_version)
        );
CREATE TABLE IF NOT EXISTS analysis_pattern_proposals (
            proposal_id TEXT PRIMARY KEY,
            analysis_build_id TEXT NOT NULL,
            kg_build_id TEXT NOT NULL,
            pattern_spec TEXT NOT NULL,
            binding_examples TEXT NOT NULL,
            semantic_pass_rate REAL NOT NULL,
            signal_execution_pass_rate REAL NOT NULL,
            claim_plan_pass_rate REAL NOT NULL,
            heldout_pass_rate REAL NOT NULL,
            status TEXT NOT NULL,
            proposal_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
CREATE TABLE IF NOT EXISTS analysis_pattern_catalog_releases (
            catalog_release_id TEXT PRIMARY KEY,
            catalog_version TEXT NOT NULL,
            source_analysis_build_id TEXT NOT NULL,
            catalog_manifest TEXT NOT NULL,
            catalog_manifest_hash TEXT NOT NULL,
            compatibility_contract TEXT NOT NULL,
            status TEXT NOT NULL,
            published_at TEXT,
            published_by TEXT
        );
CREATE TABLE IF NOT EXISTS analysis_pattern_catalog_entries (
            catalog_entry_id TEXT PRIMARY KEY,
            catalog_release_id TEXT NOT NULL,
            analysis_pattern_id TEXT NOT NULL,
            pattern_version INTEGER NOT NULL,
            pattern_spec TEXT NOT NULL,
            pattern_hash TEXT NOT NULL,
            status TEXT NOT NULL,
            UNIQUE(catalog_release_id, analysis_pattern_id, pattern_version)
        );
CREATE TABLE IF NOT EXISTS analysis_candidates (
            candidate_id TEXT PRIMARY KEY,
            stable_candidate_id TEXT NOT NULL,
            analysis_build_id TEXT NOT NULL,
            analysis_pattern_id TEXT NOT NULL,
            pattern_version INTEGER NOT NULL,
            pattern_hash TEXT NOT NULL,
            entity_ids TEXT NOT NULL,
            metric_ids TEXT NOT NULL,
            period_scope TEXT NOT NULL,
            scope_definition TEXT,
            peer_scope_type TEXT,
            peer_scope_id TEXT,
            expected_scope_entity_ids TEXT NOT NULL,
            scope_membership_hash TEXT,
            scope_eligibility_policy_hash TEXT,
            peer_scope_contract TEXT NOT NULL,
            signal_ids TEXT NOT NULL,
            evidence_bundle_id TEXT NOT NULL,
            claim_plan_id TEXT NOT NULL,
            instruction TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            difficulty_features TEXT NOT NULL,
            eligibility_status TEXT NOT NULL,
            rejection_reasons TEXT NOT NULL,
            candidate_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
CREATE TABLE IF NOT EXISTS analysis_evidence_bundles (
            evidence_bundle_id TEXT PRIMARY KEY,
            analysis_build_id TEXT NOT NULL,
            kg_build_id TEXT NOT NULL,
            entity_ids TEXT NOT NULL,
            metric_ids TEXT NOT NULL,
            period_scope TEXT NOT NULL,
            scope_definition TEXT,
            peer_scope_type TEXT,
            peer_scope_id TEXT,
            expected_scope_entity_ids TEXT NOT NULL,
            scope_membership_hash TEXT,
            scope_eligibility_policy_hash TEXT,
            peer_scope_contract TEXT NOT NULL,
            fact_ids TEXT NOT NULL,
            derived_fact_ids TEXT NOT NULL,
            signal_ids TEXT NOT NULL,
            source_document_ids TEXT NOT NULL,
            raw_object_ids TEXT NOT NULL,
            evidence_node_ids TEXT NOT NULL,
            evidence_edges TEXT NOT NULL,
            evidence_components TEXT NOT NULL,
            supporting_evidence TEXT NOT NULL,
            counter_evidence TEXT NOT NULL,
            coverage_report TEXT NOT NULL,
            bundle_hash TEXT NOT NULL
        );
CREATE TABLE IF NOT EXISTS analysis_claim_plans (
            claim_plan_id TEXT PRIMARY KEY,
            analysis_build_id TEXT NOT NULL,
            candidate_id TEXT NOT NULL,
            claim_graph TEXT NOT NULL,
            valid_conclusion_set TEXT NOT NULL,
            invalid_conclusions TEXT NOT NULL,
            mandatory_claim_ids TEXT NOT NULL,
            optional_claim_ids TEXT NOT NULL,
            forbidden_claim_types TEXT NOT NULL,
            required_caveat_ids TEXT NOT NULL,
            selected_conclusion_id TEXT NOT NULL,
            plan_hash TEXT NOT NULL,
            validation_status TEXT NOT NULL
        );
CREATE TABLE IF NOT EXISTS analysis_samples (
            analysis_sample_id TEXT PRIMARY KEY,
            stable_analysis_sample_id TEXT NOT NULL,
            analysis_semantic_cluster_id TEXT NOT NULL,
            evidence_bundle_cluster_id TEXT NOT NULL,
            signal_composition_id TEXT NOT NULL,
            claim_schema_id TEXT NOT NULL,
            conclusion_family_id TEXT NOT NULL,
            analysis_build_id TEXT NOT NULL,
            candidate_id TEXT NOT NULL,
            instruction TEXT NOT NULL,
            analysis_text TEXT NOT NULL,
            selected_conclusion_id TEXT NOT NULL,
            conclusion_text TEXT,
            conclusion_semantic_frame TEXT,
            conclusion_surface_form_id TEXT,
            claim_alignment TEXT NOT NULL,
            numeric_slots TEXT,
            generation_metadata TEXT,
            caveats TEXT NOT NULL,
            rubric TEXT NOT NULL,
            generation_method TEXT NOT NULL,
            validation_status TEXT NOT NULL,
            split TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
CREATE TABLE IF NOT EXISTS analysis_llm_calls (
            llm_call_id TEXT PRIMARY KEY,
            analysis_build_id TEXT NOT NULL,
            candidate_id TEXT NOT NULL,
            analysis_sample_id TEXT NOT NULL,
            provider TEXT,
            endpoint_host TEXT,
            model_requested TEXT,
            response_model TEXT,
            response_id TEXT,
            request_hash TEXT,
            response_hash TEXT,
            http_status INTEGER,
            http_success INTEGER NOT NULL,
            json_valid INTEGER NOT NULL,
            structured_response_valid INTEGER NOT NULL,
            controlled_generation INTEGER NOT NULL,
            latency_ms REAL,
            prompt_tokens BIGINT,
            completion_tokens BIGINT,
            total_tokens BIGINT,
            estimated_cost REAL,
            fallback_reason TEXT,
            error_type TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
CREATE TABLE IF NOT EXISTS analysis_quality_checks (
            check_id TEXT PRIMARY KEY,
            analysis_sample_id TEXT NOT NULL,
            analysis_build_id TEXT NOT NULL,
            check_name TEXT NOT NULL,
            check_status TEXT NOT NULL,
            observed_value TEXT,
            expected_value TEXT,
            message TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
CREATE INDEX IF NOT EXISTS idx_analysis_builds_kg_status ON analysis_builds(kg_build_id, status);
CREATE INDEX IF NOT EXISTS idx_signal_instances_build_spec ON financial_signal_instances(analysis_build_id, signal_spec_id, recompute_status);
CREATE INDEX IF NOT EXISTS idx_analysis_candidates_build_pattern ON analysis_candidates(analysis_build_id, analysis_pattern_id, eligibility_status);
CREATE INDEX IF NOT EXISTS idx_analysis_samples_build_status ON analysis_samples(analysis_build_id, validation_status);
CREATE INDEX IF NOT EXISTS idx_analysis_samples_cluster ON analysis_samples(analysis_semantic_cluster_id);
CREATE INDEX IF NOT EXISTS idx_analysis_checks_build_status ON analysis_quality_checks(analysis_build_id, check_status);
CREATE INDEX IF NOT EXISTS idx_analysis_llm_calls_build_status ON analysis_llm_calls(analysis_build_id, controlled_generation, fallback_reason);

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
    },
    {
        "source_id": "bse_disclosures",
        "source_name": "Beijing Stock Exchange Disclosures",
        "source_type": "pdf",
        "authority_level": "S1_official",
        "market": "CN",
        "provider": "BSE",
        "base_url": "https://www.bse.cn/disclosure/announcement.html",
        "access_method": "official_public_endpoint",
        "update_frequency": "real_time_daily",
        "license_note": "BSE public website terms and market-data licensing rules apply.",
        "rate_limit_note": "Use polite, low-rate requests and retain source URLs."
    },
    {
        "source_id": "hkex_disclosures",
        "source_name": "HKEXnews Listed Company Annual Reports",
        "source_type": "pdf",
        "authority_level": "S1_official",
        "market": "HK",
        "provider": "HKEX",
        "base_url": "https://www.hkexnews.hk/index.htm",
        "access_method": "official_public_endpoint",
        "update_frequency": "real_time_daily",
        "license_note": "HKEX website terms and market-data licensing rules apply.",
        "rate_limit_note": "Use polite, low-rate requests and retain source URLs."
    },
    {
        "source_id": "nbs_official_statistics",
        "source_name": "National Bureau of Statistics of China Releases",
        "source_type": "html_pdf_xlsx",
        "authority_level": "S1_official",
        "market": "CN",
        "provider": "NBS",
        "base_url": "https://www.stats.gov.cn/sj/zxfb/",
        "access_method": "official_publication_download",
        "update_frequency": "monthly_quarterly_annual",
        "license_note": "National Bureau of Statistics public website terms apply.",
        "rate_limit_note": "Use immutable release URLs and polite low-rate requests."
    },
    {
        "source_id": "pboc_official_statistics",
        "source_name": "People's Bank of China Statistical Releases",
        "source_type": "html_pdf_xlsx",
        "authority_level": "S1_official",
        "market": "CN",
        "provider": "PBOC",
        "base_url": "https://www.pbc.gov.cn/diaochatongjisi/",
        "access_method": "official_publication_download",
        "update_frequency": "monthly_quarterly_annual",
        "license_note": "People's Bank of China public website terms apply.",
        "rate_limit_note": "Use immutable release URLs and polite low-rate requests."
    },
    {
        "source_id": "safe_official_statistics",
        "source_name": "State Administration of Foreign Exchange Statistics",
        "source_type": "html_pdf_xlsx",
        "authority_level": "S1_official",
        "market": "CN_Global",
        "provider": "SAFE",
        "base_url": "https://www.safe.gov.cn/safe/tjsj1/",
        "access_method": "official_publication_download",
        "update_frequency": "monthly_quarterly_annual",
        "license_note": "SAFE public website terms apply.",
        "rate_limit_note": "Use immutable release URLs and polite low-rate requests."
    },
    {
        "source_id": "sse_market_statistics",
        "source_name": "Shanghai Stock Exchange Market Statistics",
        "source_type": "html_pdf",
        "authority_level": "S1_official",
        "market": "CN",
        "provider": "SSE",
        "base_url": "https://www.sse.com.cn/market/stockdata/statistic/",
        "access_method": "official_publication_download",
        "update_frequency": "daily_monthly_annual",
        "license_note": "SSE website and market-data licensing terms apply.",
        "rate_limit_note": "Use public statistical publications at a polite rate."
    },
    {
        "source_id": "szse_market_statistics",
        "source_name": "Shenzhen Stock Exchange Market Statistics",
        "source_type": "html_pdf",
        "authority_level": "S1_official",
        "market": "CN",
        "provider": "SZSE",
        "base_url": "https://www.szse.cn/market/periodical/",
        "access_method": "official_publication_download",
        "update_frequency": "daily_monthly_annual",
        "license_note": "SZSE website and market-data licensing terms apply.",
        "rate_limit_note": "Use public statistical publications at a polite rate."
    },
    {
        "source_id": "bse_market_statistics",
        "source_name": "Beijing Stock Exchange Market and Index Statistics",
        "source_type": "html_pdf",
        "authority_level": "S1_official",
        "market": "CN",
        "provider": "BSE",
        "base_url": "https://www.bse.cn/static/statisticdata.html",
        "access_method": "official_publication_download",
        "update_frequency": "daily_weekly_monthly",
        "license_note": "BSE website and market-data licensing terms apply.",
        "rate_limit_note": "Use public statistical publications at a polite rate."
    },
    {
        "source_id": "csi_index_publications",
        "source_name": "China Securities Index Official Publications",
        "source_type": "html_pdf_xlsx",
        "authority_level": "S1_official",
        "market": "CN",
        "provider": "CSI",
        "base_url": "https://www.csindex.com.cn/",
        "access_method": "official_publication_download",
        "update_frequency": "event_driven_semiannual",
        "license_note": "China Securities Index website and index-data terms apply.",
        "rate_limit_note": "Use public constituent notices at a polite rate."
    }
]
