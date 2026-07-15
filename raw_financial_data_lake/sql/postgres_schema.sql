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
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ingestion_jobs (
    job_id              TEXT PRIMARY KEY,
    source_id           TEXT REFERENCES source_registry(source_id),
    job_type            TEXT,
    target_scope        JSONB,
    start_time          TIMESTAMPTZ,
    end_time            TIMESTAMPTZ,
    status              TEXT,
    records_found       INTEGER,
    records_saved       INTEGER,
    error_message       TEXT,
    config              JSONB
);

CREATE TABLE IF NOT EXISTS raw_objects (
    raw_object_id       TEXT PRIMARY KEY,
    source_id           TEXT REFERENCES source_registry(source_id),
    job_id              TEXT REFERENCES ingestion_jobs(job_id),
    object_type         TEXT,
    storage_uri         TEXT,
    original_url        TEXT,
    request_params      JSONB,
    response_headers    JSONB,
    response_status     INTEGER,
    content_sha256      TEXT,
    content_size_bytes  BIGINT,
    compression         TEXT,
    retrieval_time      TIMESTAMPTZ,
    source_publish_date DATE,
    source_update_time  TIMESTAMPTZ,
    parse_status        TEXT DEFAULT 'unparsed',
    validation_status   TEXT DEFAULT 'unchecked',
    notes               TEXT
);

CREATE INDEX IF NOT EXISTS idx_raw_objects_source_id ON raw_objects(source_id);
CREATE INDEX IF NOT EXISTS idx_raw_objects_sha256 ON raw_objects(content_sha256);
CREATE INDEX IF NOT EXISTS idx_raw_objects_original_url ON raw_objects(original_url);
CREATE UNIQUE INDEX IF NOT EXISTS idx_raw_objects_url_hash ON raw_objects(source_id, original_url, content_sha256);

CREATE TABLE IF NOT EXISTS raw_records (
    raw_record_id       TEXT PRIMARY KEY,
    raw_object_id       TEXT REFERENCES raw_objects(raw_object_id),
    source_id           TEXT REFERENCES source_registry(source_id),
    record_key          TEXT,
    record_type         TEXT,
    record_json         JSONB,
    entity_hint         TEXT,
    metric_hint         TEXT,
    period_hint         TEXT,
    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_raw_records_source_id ON raw_records(source_id);
CREATE INDEX IF NOT EXISTS idx_raw_records_record_key ON raw_records(record_key);

CREATE TABLE IF NOT EXISTS source_entities (
    source_entity_id    TEXT PRIMARY KEY,
    source_id           TEXT REFERENCES source_registry(source_id),
    source_code         TEXT,
    source_name         TEXT,
    aliases             TEXT[],
    market              TEXT,
    raw_metadata        JSONB,
    first_seen_at       TIMESTAMPTZ,
    last_seen_at        TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_source_entities_source_code ON source_entities(source_id, source_code);

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
    created_at          TIMESTAMPTZ DEFAULT now(),
    updated_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_metrics_category ON metrics(metric_category);
CREATE INDEX IF NOT EXISTS idx_metrics_statement_type ON metrics(statement_type);

CREATE TABLE IF NOT EXISTS metric_alias_map (
    alias_id            TEXT PRIMARY KEY,
    metric_id           TEXT REFERENCES metrics(metric_id),
    source_id           TEXT REFERENCES source_registry(source_id),
    raw_field_name      TEXT,
    raw_concept_name    TEXT,
    confidence_score    DOUBLE PRECISION,
    created_at          TIMESTAMPTZ DEFAULT now()
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
    created_at          TIMESTAMPTZ DEFAULT now(),
    updated_at          TIMESTAMPTZ DEFAULT now()
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
    confidence_score    DOUBLE PRECISION,
    created_at          TIMESTAMPTZ DEFAULT now()
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
    created_at         TIMESTAMPTZ DEFAULT now(),
    updated_at         TIMESTAMPTZ DEFAULT now()
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
    confidence_score   DOUBLE PRECISION,
    valid_from         TEXT,
    valid_to           TEXT,
    notes              TEXT,
    build_id           TEXT,
    is_active          INTEGER DEFAULT 1,
    superseded_by      TEXT,
    created_at         TIMESTAMPTZ DEFAULT now()
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
    created_at         TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_source_series_entity_map_source_series ON source_series_entity_map(source_id, series_id);
CREATE INDEX IF NOT EXISTS idx_source_series_entity_map_metric ON source_series_entity_map(metric_id);
CREATE INDEX IF NOT EXISTS idx_source_series_entity_map_target ON source_series_entity_map(applies_to_entity_id, instrument_entity_id);

CREATE TABLE IF NOT EXISTS source_metric_definitions (
    definition_id       TEXT PRIMARY KEY,
    source_id           TEXT REFERENCES source_registry(source_id),
    metric_id           TEXT REFERENCES metrics(metric_id),
    raw_concept_name    TEXT,
    definition_text     TEXT,
    unit_rule           TEXT,
    frequency           TEXT,
    vintage_policy      TEXT,
    is_forecast         BOOLEAN,
    comparable_to_metric_id TEXT,
    comparability_level TEXT,
    notes               TEXT,
    build_id            TEXT,
    is_active           INTEGER DEFAULT 1,
    superseded_by       TEXT,
    created_at          TIMESTAMPTZ DEFAULT now()
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
    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_time_series_frequency_source_series ON time_series_frequency_map(source_id, series_id);
CREATE INDEX IF NOT EXISTS idx_time_series_frequency_metric ON time_series_frequency_map(metric_id);

CREATE TABLE IF NOT EXISTS atomic_facts (
    fact_id             TEXT PRIMARY KEY,
    stable_fact_id      TEXT,
    build_id            TEXT,
    raw_snapshot_id     TEXT,
    is_active           INTEGER DEFAULT 1,
    superseded_by       TEXT,
    entity_id           TEXT REFERENCES canonical_entities(entity_id),
    metric_id           TEXT REFERENCES metrics(metric_id),
    value               NUMERIC,
    value_type          TEXT,
    unit                TEXT,
    currency            TEXT,
    period_start        DATE,
    period_end          DATE,
    fiscal_year         INTEGER,
    fiscal_quarter      TEXT,
    as_of_date          DATE,
    report_date         DATE,
    source_id           TEXT REFERENCES source_registry(source_id),
    raw_object_id       TEXT REFERENCES raw_objects(raw_object_id),
    source_field_name   TEXT,
    source_page_or_table TEXT,
    extraction_method   TEXT,
    confidence_score    DOUBLE PRECISION,
    verification_status TEXT,
    tolerance           DOUBLE PRECISION,
    notes               TEXT,
    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_atomic_facts_entity_id ON atomic_facts(entity_id);
CREATE INDEX IF NOT EXISTS idx_atomic_facts_metric_id ON atomic_facts(metric_id);
CREATE INDEX IF NOT EXISTS idx_atomic_facts_period_end ON atomic_facts(period_end);
CREATE INDEX IF NOT EXISTS idx_atomic_facts_source ON atomic_facts(source_id, raw_object_id);
CREATE INDEX IF NOT EXISTS idx_atomic_facts_verification ON atomic_facts(verification_status);

CREATE TABLE IF NOT EXISTS standardized_facts (
    fact_id             TEXT PRIMARY KEY REFERENCES atomic_facts(fact_id),
    stable_fact_id      TEXT,
    build_id            TEXT,
    raw_snapshot_id     TEXT,
    is_active           INTEGER DEFAULT 1,
    superseded_by       TEXT,
    entity_id           TEXT REFERENCES canonical_entities(entity_id),
    metric_id           TEXT REFERENCES metrics(metric_id),
    normalized_value    NUMERIC,
    normalized_unit     TEXT,
    normalized_currency TEXT,
    value_scale         TEXT,
    period_start        DATE,
    period_end          DATE,
    calendar_year       INTEGER,
    fiscal_year         INTEGER,
    fiscal_quarter      TEXT,
    time_basis          TEXT,
    metric_period_type  TEXT,
    source_definition_id TEXT REFERENCES source_metric_definitions(definition_id),
    frequency           TEXT,
    seasonal_adjustment TEXT,
    vintage_policy      TEXT,
    is_forecast         BOOLEAN,
    comparability_level TEXT,
    as_of_date          DATE,
    report_date         DATE,
    source_id           TEXT REFERENCES source_registry(source_id),
    raw_object_id       TEXT REFERENCES raw_objects(raw_object_id),
    verification_status TEXT,
    graph_ready          BOOLEAN DEFAULT FALSE,
    graph_ready_reason   TEXT,
    validation_flags    JSONB,
    conflict_group_id   TEXT,
    raw_equivalence_group_id TEXT,
    semantic_equivalence_group_id TEXT,
    confidence_score    DOUBLE PRECISION,
    notes               TEXT,
    updated_at          TIMESTAMPTZ DEFAULT now()
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
    created_at          TIMESTAMPTZ DEFAULT now()
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
    input_fact_ids      JSONB,
    entity_scope        JSONB,
    metric_scope        JSONB,
    time_scope          JSONB,
    scope_type          TEXT,
    scope_id            TEXT,
    scope_definition    TEXT,
    scope_entity_ids    JSONB,
    scope_source        TEXT,
    calculation_code    TEXT,
    output_value        NUMERIC,
    output_table        JSONB,
    unit                TEXT,
    tolerance           DOUBLE PRECISION,
    verification_status TEXT,
    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_derived_facts_type ON derived_facts(derived_type);
CREATE INDEX IF NOT EXISTS idx_derived_facts_status ON derived_facts(verification_status);





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
    confidence_score    DOUBLE PRECISION,
    created_at          TIMESTAMPTZ DEFAULT now()
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
    raw_table_json      JSONB,
    extraction_method   TEXT,
    confidence_score    DOUBLE PRECISION,
    created_at          TIMESTAMPTZ DEFAULT now()
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
    confidence_score    DOUBLE PRECISION,
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
    created_at          TIMESTAMPTZ DEFAULT now()
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



CREATE TABLE IF NOT EXISTS data_coverage_report (
    source_id           TEXT PRIMARY KEY,
    entity_count        INTEGER,
    metric_count        INTEGER,
    min_date            DATE,
    max_date            DATE,
    object_count        INTEGER,
    missing_rate        DOUBLE PRECISION,
    parse_ready         BOOLEAN,
    quality_level       TEXT,
    updated_at          TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw_dataset_snapshots (
    snapshot_id         TEXT PRIMARY KEY,
    source_id           TEXT REFERENCES source_registry(source_id),
    snapshot_date       DATE,
    storage_prefix      TEXT,
    object_count        INTEGER,
    total_size_bytes    BIGINT,
    manifest_uri        TEXT,
    checksum_uri        TEXT,
    created_at          TIMESTAMPTZ DEFAULT now()
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
            generator_version TEXT,
            git_commit_sha TEXT,
            split_policy_hash TEXT,
            status TEXT NOT NULL,
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            candidate_count BIGINT DEFAULT 0,
            passed_count BIGINT DEFAULT 0,
            sample_count BIGINT DEFAULT 0,
            quality_status TEXT,
            is_active BOOLEAN DEFAULT FALSE,
            superseded_by TEXT,
            notes JSONB
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
            required_slots JSONB NOT NULL,
            answer_type TEXT NOT NULL,
            difficulty_base TEXT NOT NULL,
            is_active BOOLEAN DEFAULT TRUE
        );
CREATE TABLE IF NOT EXISTS qa_graph_patterns (
            pattern_key TEXT PRIMARY KEY,
            pattern_id TEXT NOT NULL,
            pattern_version INTEGER NOT NULL,
            pattern_family TEXT NOT NULL,
            node_constraints JSONB NOT NULL,
            edge_constraints JSONB NOT NULL,
            semantic_constraints JSONB NOT NULL,
            operator_template JSONB NOT NULL,
            answer_schema JSONB NOT NULL,
            difficulty_base TEXT NOT NULL,
            question_intents JSONB NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
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
            operation_plan_id TEXT,
            graph_features JSONB,
            difficulty_score REAL,
            answer_schema JSONB,
            question_intent TEXT,
            entity_ids JSONB NOT NULL,
            metric_ids JSONB NOT NULL,
            time_scope JSONB NOT NULL,
            entity_scope JSONB NOT NULL,
            source_fact_ids JSONB NOT NULL,
            source_derived_ids JSONB NOT NULL,
            source_document_ids JSONB NOT NULL,
            raw_object_ids JSONB NOT NULL,
            canonical_semantics JSONB NOT NULL,
            derived_payload JSONB NOT NULL,
            recomputed_payload JSONB NOT NULL,
            answer_payload JSONB NOT NULL,
            kg_path JSONB NOT NULL,
            eligibility_status TEXT NOT NULL,
            rejection_reasons JSONB NOT NULL,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );
CREATE TABLE IF NOT EXISTS qa_operation_plans (
            plan_id TEXT PRIMARY KEY,
            qa_build_id TEXT NOT NULL,
            candidate_id TEXT NOT NULL,
            pattern_id TEXT NOT NULL,
            pattern_version INTEGER NOT NULL,
            operator_dag JSONB NOT NULL,
            input_bindings JSONB NOT NULL,
            intermediate_results JSONB NOT NULL,
            output_schema JSONB NOT NULL,
            recompute_status TEXT NOT NULL,
            validation_errors JSONB NOT NULL,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
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
            answer_value JSONB NOT NULL,
            answer_text TEXT NOT NULL,
            unit TEXT,
            currency TEXT,
            rubric JSONB NOT NULL,
            source_metadata JSONB NOT NULL,
            generation_method TEXT NOT NULL,
            validation_status TEXT NOT NULL,
            split TEXT,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );
CREATE TABLE IF NOT EXISTS qa_evidence_paths (
            path_id TEXT PRIMARY KEY,
            qa_id TEXT NOT NULL,
            path_type TEXT NOT NULL,
            ordered_node_ids JSONB NOT NULL,
            ordered_edge_ids JSONB NOT NULL,
            evidence_node_ids JSONB NOT NULL,
            evidence_edges JSONB NOT NULL,
            evidence_components JSONB NOT NULL,
            source_fact_ids JSONB NOT NULL,
            source_derived_ids JSONB NOT NULL,
            raw_object_ids JSONB NOT NULL,
            source_document_ids JSONB NOT NULL
        );
CREATE TABLE IF NOT EXISTS qa_quality_checks (
            check_id TEXT PRIMARY KEY,
            qa_id TEXT NOT NULL,
            qa_build_id TEXT NOT NULL,
            check_name TEXT NOT NULL,
            check_status TEXT NOT NULL,
            observed_value JSONB,
            expected_value JSONB,
            message TEXT,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );
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
