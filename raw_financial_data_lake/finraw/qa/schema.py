from __future__ import annotations

from finraw.db.client import DBProtocol


def _ddl(json_type: str, bool_type: str, timestamp_type: str) -> list[str]:
    false_literal = "FALSE" if bool_type == "BOOLEAN" else "0"
    true_literal = "TRUE" if bool_type == "BOOLEAN" else "1"
    return [
        f"""
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
            started_at {timestamp_type},
            completed_at {timestamp_type},
            candidate_count BIGINT DEFAULT 0,
            passed_count BIGINT DEFAULT 0,
            sample_count BIGINT DEFAULT 0,
            quality_status TEXT,
            is_active {bool_type} DEFAULT {false_literal},
            superseded_by TEXT,
            notes {json_type}
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS qa_templates (
            template_id TEXT PRIMARY KEY,
            task_family TEXT NOT NULL,
            source_type TEXT,
            entity_type TEXT,
            metric_category TEXT,
            period_type TEXT,
            language TEXT NOT NULL,
            template_text TEXT NOT NULL,
            required_slots {json_type} NOT NULL,
            answer_type TEXT NOT NULL,
            difficulty_base TEXT NOT NULL,
            is_active {bool_type} DEFAULT {true_literal}
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS qa_candidates (
            candidate_id TEXT PRIMARY KEY,
            stable_candidate_id TEXT NOT NULL,
            qa_build_id TEXT NOT NULL,
            task_family TEXT NOT NULL,
            task_subtype TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            entity_ids {json_type} NOT NULL,
            metric_ids {json_type} NOT NULL,
            time_scope {json_type} NOT NULL,
            entity_scope {json_type} NOT NULL,
            source_fact_ids {json_type} NOT NULL,
            source_derived_ids {json_type} NOT NULL,
            source_document_ids {json_type} NOT NULL,
            raw_object_ids {json_type} NOT NULL,
            canonical_semantics {json_type} NOT NULL,
            answer_payload {json_type} NOT NULL,
            kg_path {json_type} NOT NULL,
            eligibility_status TEXT NOT NULL,
            rejection_reasons {json_type} NOT NULL,
            created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS qa_samples (
            qa_id TEXT PRIMARY KEY,
            stable_qa_id TEXT NOT NULL,
            qa_group_id TEXT NOT NULL,
            semantic_cluster_id TEXT NOT NULL,
            qa_build_id TEXT NOT NULL,
            candidate_id TEXT NOT NULL,
            template_id TEXT,
            template_hash TEXT,
            task_family TEXT NOT NULL,
            task_subtype TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            language TEXT NOT NULL,
            question TEXT NOT NULL,
            canonical_question TEXT NOT NULL,
            answer_type TEXT NOT NULL,
            answer_value {json_type} NOT NULL,
            answer_text TEXT NOT NULL,
            unit TEXT,
            currency TEXT,
            rubric {json_type} NOT NULL,
            source_metadata {json_type} NOT NULL,
            generation_method TEXT NOT NULL,
            validation_status TEXT NOT NULL,
            split TEXT,
            created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS qa_evidence_paths (
            path_id TEXT PRIMARY KEY,
            qa_id TEXT NOT NULL,
            path_type TEXT NOT NULL,
            ordered_node_ids {json_type} NOT NULL,
            ordered_edge_ids {json_type} NOT NULL,
            source_fact_ids {json_type} NOT NULL,
            source_derived_ids {json_type} NOT NULL,
            raw_object_ids {json_type} NOT NULL,
            source_document_ids {json_type} NOT NULL
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS qa_quality_checks (
            check_id TEXT PRIMARY KEY,
            qa_id TEXT NOT NULL,
            qa_build_id TEXT NOT NULL,
            check_name TEXT NOT NULL,
            check_status TEXT NOT NULL,
            observed_value {json_type},
            expected_value {json_type},
            message TEXT,
            created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_kg_edges_build_rel_src ON kg_edges(kg_build_id, relation_type, src_node_id)",
        "CREATE INDEX IF NOT EXISTS idx_kg_edges_build_rel_dst ON kg_edges(kg_build_id, relation_type, dst_node_id)",
        "CREATE INDEX IF NOT EXISTS idx_qa_builds_kg_status ON qa_builds(kg_build_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_qa_candidates_task_status ON qa_candidates(qa_build_id, task_subtype, eligibility_status)",
        "CREATE INDEX IF NOT EXISTS idx_qa_candidates_stable ON qa_candidates(stable_candidate_id)",
        "CREATE INDEX IF NOT EXISTS idx_qa_samples_build_status ON qa_samples(qa_build_id, validation_status)",
        "CREATE INDEX IF NOT EXISTS idx_qa_samples_group_split ON qa_samples(qa_group_id, split)",
        "CREATE INDEX IF NOT EXISTS idx_qa_samples_cluster ON qa_samples(semantic_cluster_id)",
        "CREATE INDEX IF NOT EXISTS idx_qa_evidence_qa ON qa_evidence_paths(qa_id)",
        "CREATE INDEX IF NOT EXISTS idx_qa_quality_build_status ON qa_quality_checks(qa_build_id, check_status)",
    ]


def ensure_qa_schema(db: DBProtocol) -> None:
    postgres = db.__class__.__name__ == "PostgresMetadataDB"
    statements = _ddl(
        "JSONB" if postgres else "TEXT",
        "BOOLEAN" if postgres else "INTEGER",
        "TIMESTAMPTZ" if postgres else "TEXT",
    )
    for statement in statements:
        db.execute(statement)
    migrations = {
        "qa_builds": {
            "template_manifest_hash": "TEXT",
            "generator_version": "TEXT",
            "git_commit_sha": "TEXT",
            "split_policy_hash": "TEXT",
        },
        "qa_samples": {"template_id": "TEXT", "template_hash": "TEXT"},
    }
    for table, columns in migrations.items():
        for column, column_type in columns.items():
            try:
                db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")
            except Exception as exc:
                message = str(exc).lower()
                if (
                    "duplicate column" not in message
                    and "already exists" not in message
                ):
                    raise
