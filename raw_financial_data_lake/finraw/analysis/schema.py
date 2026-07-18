from __future__ import annotations

from finraw.db.client import DBProtocol


def _ddl(json_type: str, bool_type: str, timestamp_type: str) -> list[str]:
    false_literal = "FALSE" if bool_type == "BOOLEAN" else "0"
    true_literal = "TRUE" if bool_type == "BOOLEAN" else "1"
    return [
        f"""
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
            started_at {timestamp_type},
            completed_at {timestamp_type},
            candidate_count BIGINT DEFAULT 0,
            signal_count BIGINT DEFAULT 0,
            sample_count BIGINT DEFAULT 0,
            passed_count BIGINT DEFAULT 0,
            quality_status TEXT,
            is_active {bool_type} DEFAULT {false_literal},
            superseded_by TEXT,
            notes {json_type} NOT NULL
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS financial_signal_specs (
            signal_spec_id TEXT PRIMARY KEY,
            signal_type TEXT NOT NULL,
            signal_version INTEGER NOT NULL,
            signal_category TEXT NOT NULL,
            input_roles {json_type} NOT NULL,
            required_metrics {json_type} NOT NULL,
            required_periods INTEGER NOT NULL,
            required_scope {json_type} NOT NULL,
            semantic_constraints {json_type} NOT NULL,
            operator_dag {json_type} NOT NULL,
            output_schema {json_type} NOT NULL,
            direction_policy {json_type} NOT NULL,
            strength_policy {json_type} NOT NULL,
            caveat_policy {json_type} NOT NULL,
            signal_hash TEXT NOT NULL,
            is_active {bool_type} DEFAULT {true_literal}
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS financial_signal_instances (
            signal_id TEXT PRIMARY KEY,
            signal_spec_id TEXT NOT NULL,
            analysis_build_id TEXT NOT NULL,
            entity_ids {json_type} NOT NULL,
            metric_ids {json_type} NOT NULL,
            period_scope {json_type} NOT NULL,
            scope_definition TEXT,
            input_fact_ids {json_type} NOT NULL,
            input_derived_ids {json_type} NOT NULL,
            operator_plan {json_type} NOT NULL,
            intermediate_results {json_type} NOT NULL,
            signal_payload {json_type} NOT NULL,
            direction TEXT NOT NULL,
            strength TEXT NOT NULL,
            confidence REAL NOT NULL,
            supporting_evidence_ids {json_type} NOT NULL,
            counter_evidence_ids {json_type} NOT NULL,
            recompute_status TEXT NOT NULL,
            signal_hash TEXT NOT NULL,
            created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS analysis_patterns (
            pattern_key TEXT PRIMARY KEY,
            analysis_pattern_id TEXT NOT NULL,
            pattern_version INTEGER NOT NULL,
            analysis_family TEXT NOT NULL,
            question_intents {json_type} NOT NULL,
            required_signal_roles {json_type} NOT NULL,
            optional_signal_roles {json_type} NOT NULL,
            counter_signal_roles {json_type} NOT NULL,
            evidence_constraints {json_type} NOT NULL,
            claim_schema {json_type} NOT NULL,
            conclusion_policy {json_type} NOT NULL,
            forbidden_claim_types {json_type} NOT NULL,
            difficulty_base TEXT NOT NULL,
            instruction_template TEXT NOT NULL,
            pattern_hash TEXT NOT NULL,
            is_active {bool_type} DEFAULT {true_literal},
            UNIQUE(analysis_pattern_id, pattern_version)
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS analysis_pattern_proposals (
            proposal_id TEXT PRIMARY KEY,
            analysis_build_id TEXT NOT NULL,
            kg_build_id TEXT NOT NULL,
            pattern_spec {json_type} NOT NULL,
            binding_examples {json_type} NOT NULL,
            semantic_pass_rate REAL NOT NULL,
            signal_execution_pass_rate REAL NOT NULL,
            claim_plan_pass_rate REAL NOT NULL,
            heldout_pass_rate REAL NOT NULL,
            status TEXT NOT NULL,
            proposal_hash TEXT NOT NULL,
            created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS analysis_pattern_catalog_releases (
            catalog_release_id TEXT PRIMARY KEY,
            catalog_version TEXT NOT NULL,
            source_analysis_build_id TEXT NOT NULL,
            catalog_manifest {json_type} NOT NULL,
            catalog_manifest_hash TEXT NOT NULL,
            compatibility_contract {json_type} NOT NULL,
            status TEXT NOT NULL,
            published_at {timestamp_type},
            published_by TEXT
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS analysis_pattern_catalog_entries (
            catalog_entry_id TEXT PRIMARY KEY,
            catalog_release_id TEXT NOT NULL,
            analysis_pattern_id TEXT NOT NULL,
            pattern_version INTEGER NOT NULL,
            pattern_spec {json_type} NOT NULL,
            pattern_hash TEXT NOT NULL,
            status TEXT NOT NULL,
            UNIQUE(catalog_release_id, analysis_pattern_id, pattern_version)
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS analysis_candidates (
            candidate_id TEXT PRIMARY KEY,
            stable_candidate_id TEXT NOT NULL,
            analysis_build_id TEXT NOT NULL,
            analysis_pattern_id TEXT NOT NULL,
            pattern_version INTEGER NOT NULL,
            pattern_hash TEXT NOT NULL,
            entity_ids {json_type} NOT NULL,
            metric_ids {json_type} NOT NULL,
            period_scope {json_type} NOT NULL,
            scope_definition TEXT,
            signal_ids {json_type} NOT NULL,
            evidence_bundle_id TEXT NOT NULL,
            claim_plan_id TEXT NOT NULL,
            instruction TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            difficulty_features {json_type} NOT NULL,
            eligibility_status TEXT NOT NULL,
            rejection_reasons {json_type} NOT NULL,
            candidate_hash TEXT NOT NULL,
            created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS analysis_evidence_bundles (
            evidence_bundle_id TEXT PRIMARY KEY,
            analysis_build_id TEXT NOT NULL,
            kg_build_id TEXT NOT NULL,
            entity_ids {json_type} NOT NULL,
            metric_ids {json_type} NOT NULL,
            period_scope {json_type} NOT NULL,
            scope_definition TEXT,
            fact_ids {json_type} NOT NULL,
            derived_fact_ids {json_type} NOT NULL,
            signal_ids {json_type} NOT NULL,
            source_document_ids {json_type} NOT NULL,
            raw_object_ids {json_type} NOT NULL,
            evidence_node_ids {json_type} NOT NULL,
            evidence_edges {json_type} NOT NULL,
            evidence_components {json_type} NOT NULL,
            supporting_evidence {json_type} NOT NULL,
            counter_evidence {json_type} NOT NULL,
            coverage_report {json_type} NOT NULL,
            bundle_hash TEXT NOT NULL
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS analysis_claim_plans (
            claim_plan_id TEXT PRIMARY KEY,
            analysis_build_id TEXT NOT NULL,
            candidate_id TEXT NOT NULL,
            claim_graph {json_type} NOT NULL,
            valid_conclusion_set {json_type} NOT NULL,
            invalid_conclusions {json_type} NOT NULL,
            mandatory_claim_ids {json_type} NOT NULL,
            optional_claim_ids {json_type} NOT NULL,
            forbidden_claim_types {json_type} NOT NULL,
            selected_conclusion_id TEXT NOT NULL,
            plan_hash TEXT NOT NULL,
            validation_status TEXT NOT NULL
        )
        """,
        f"""
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
            claim_alignment {json_type} NOT NULL,
            caveats {json_type} NOT NULL,
            rubric {json_type} NOT NULL,
            generation_method TEXT NOT NULL,
            validation_status TEXT NOT NULL,
            split TEXT,
            created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS analysis_quality_checks (
            check_id TEXT PRIMARY KEY,
            analysis_sample_id TEXT NOT NULL,
            analysis_build_id TEXT NOT NULL,
            check_name TEXT NOT NULL,
            check_status TEXT NOT NULL,
            observed_value {json_type},
            expected_value {json_type},
            message TEXT,
            created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_analysis_builds_kg_status ON analysis_builds(kg_build_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_signal_instances_build_spec ON financial_signal_instances(analysis_build_id, signal_spec_id, recompute_status)",
        "CREATE INDEX IF NOT EXISTS idx_analysis_candidates_build_pattern ON analysis_candidates(analysis_build_id, analysis_pattern_id, eligibility_status)",
        "CREATE INDEX IF NOT EXISTS idx_analysis_samples_build_status ON analysis_samples(analysis_build_id, validation_status)",
        "CREATE INDEX IF NOT EXISTS idx_analysis_samples_cluster ON analysis_samples(analysis_semantic_cluster_id)",
        "CREATE INDEX IF NOT EXISTS idx_analysis_checks_build_status ON analysis_quality_checks(analysis_build_id, check_status)",
    ]


def ensure_analysis_schema(db: DBProtocol) -> None:
    postgres = db.__class__.__name__ == "PostgresMetadataDB"
    for statement in _ddl(
        "JSONB" if postgres else "TEXT",
        "BOOLEAN" if postgres else "INTEGER",
        "TIMESTAMPTZ" if postgres else "TEXT",
    ):
        db.execute(statement)
