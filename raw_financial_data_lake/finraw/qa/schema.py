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
            mining_run_id TEXT,
            graph_schema_version TEXT NOT NULL,
            fact_build_id TEXT,
            derived_build_id TEXT,
            entity_build_id TEXT,
            metric_build_id TEXT,
            source_definition_build_id TEXT,
            document_build_id TEXT,
            config_hash TEXT,
            template_manifest_hash TEXT,
            pattern_manifest_hash TEXT,
            operator_manifest_hash TEXT,
            difficulty_policy_hash TEXT,
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
        CREATE TABLE IF NOT EXISTS qa_graph_patterns (
            pattern_key TEXT PRIMARY KEY,
            pattern_id TEXT NOT NULL,
            pattern_version INTEGER NOT NULL,
            pattern_family TEXT NOT NULL,
            matcher TEXT,
            pattern_hash TEXT NOT NULL,
            node_constraints {json_type} NOT NULL,
            edge_constraints {json_type} NOT NULL,
            semantic_constraints {json_type} NOT NULL,
            operator_template {json_type} NOT NULL,
            answer_schema {json_type} NOT NULL,
            difficulty_base TEXT NOT NULL,
            question_intents {json_type} NOT NULL,
            is_active {bool_type} DEFAULT {true_literal},
            UNIQUE(pattern_id, pattern_version)
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS qa_pattern_mining_runs (
            mining_run_id TEXT PRIMARY KEY,
            kg_build_id TEXT NOT NULL,
            mining_version TEXT NOT NULL,
            config_hash TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at {timestamp_type},
            completed_at {timestamp_type},
            scanned_fact_count BIGINT DEFAULT 0,
            proposal_count BIGINT DEFAULT 0,
            approved_count BIGINT DEFAULT 0,
            reviewed_at {timestamp_type},
            reviewed_by TEXT,
            approved_at {timestamp_type},
            approved_by TEXT,
            superseded_at {timestamp_type},
            superseded_by_run_id TEXT,
            lifecycle_events {json_type} NOT NULL,
            notes {json_type} NOT NULL
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS qa_pattern_proposals (
            proposal_id TEXT PRIMARY KEY,
            mining_run_id TEXT NOT NULL,
            kg_build_id TEXT NOT NULL,
            motif_family TEXT NOT NULL,
            motif_signature TEXT NOT NULL,
            proposal_semantic_id TEXT NOT NULL,
            proposal_snapshot_id TEXT NOT NULL,
            static_pattern_id TEXT,
            binding_mode TEXT NOT NULL,
            pattern_spec {json_type} NOT NULL,
            operator_dag_template {json_type} NOT NULL,
            answer_schema {json_type} NOT NULL,
            binding_examples {json_type} NOT NULL,
            heldout_bindings {json_type} NOT NULL,
            semantic_validation_results {json_type} NOT NULL,
            operation_validation_results {json_type} NOT NULL,
            lifecycle_events {json_type} NOT NULL,
            support_count BIGINT NOT NULL,
            entity_count BIGINT NOT NULL,
            metric_count BIGINT NOT NULL,
            period_count BIGINT NOT NULL,
            support_score REAL NOT NULL,
            completeness_score REAL NOT NULL,
            financial_value_score REAL NOT NULL,
            complexity_score REAL NOT NULL,
            novelty_score REAL NOT NULL,
            total_score REAL NOT NULL,
            semantic_constraint_pass_rate REAL NOT NULL,
            operation_execution_pass_rate REAL NOT NULL,
            example_binding_pass_rate REAL NOT NULL,
            heldout_binding_pass_rate REAL NOT NULL,
            static_pattern_overlap REAL NOT NULL,
            binding_diversity_score REAL NOT NULL,
            manual_review_status TEXT NOT NULL,
            status TEXT NOT NULL,
            rejection_reasons {json_type} NOT NULL,
            proposal_hash TEXT NOT NULL,
            created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS qa_pattern_compilations (
            compilation_id TEXT PRIMARY KEY,
            qa_build_id TEXT NOT NULL,
            proposal_id TEXT NOT NULL,
            proposal_hash TEXT NOT NULL,
            source_kg_build_id TEXT NOT NULL,
            target_kg_build_id TEXT NOT NULL,
            fact_build_id TEXT NOT NULL,
            compiler_version TEXT NOT NULL,
            logical_plan {json_type} NOT NULL,
            logical_plan_hash TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at {timestamp_type},
            completed_at {timestamp_type},
            discovered_binding_count BIGINT DEFAULT 0,
            semantic_valid_binding_count BIGINT DEFAULT 0,
            execution_valid_binding_count BIGINT DEFAULT 0,
            compiled_binding_count BIGINT DEFAULT 0,
            rejected_binding_count BIGINT DEFAULT 0,
            sampling_summary {json_type} NOT NULL,
            notes {json_type} NOT NULL
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS qa_compiled_bindings (
            compiled_binding_id TEXT PRIMARY KEY,
            compilation_id TEXT NOT NULL,
            qa_build_id TEXT NOT NULL,
            proposal_id TEXT NOT NULL,
            kg_build_id TEXT NOT NULL,
            binding_hash TEXT NOT NULL,
            binding {json_type} NOT NULL,
            sampling_stratum {json_type} NOT NULL,
            semantic_status TEXT NOT NULL,
            execution_status TEXT NOT NULL,
            audit_example_overlap {bool_type} DEFAULT {false_literal},
            rejection_reasons {json_type} NOT NULL,
            created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(compilation_id, binding_hash)
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS qa_graph_motif_observations (
            observation_id TEXT PRIMARY KEY,
            mining_run_id TEXT NOT NULL,
            kg_build_id TEXT NOT NULL,
            motif_family TEXT NOT NULL,
            motif_signature TEXT NOT NULL,
            node_types {json_type} NOT NULL,
            edge_types {json_type} NOT NULL,
            support_count BIGINT NOT NULL,
            distinct_root_count BIGINT NOT NULL,
            binding_examples {json_type} NOT NULL,
            status TEXT NOT NULL,
            created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP
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
            pattern_id TEXT,
            pattern_version INTEGER,
            pattern_hash TEXT,
            operation_plan_id TEXT,
            operation_plan_hash TEXT,
            mining_run_id TEXT,
            pattern_proposal_id TEXT,
            pattern_proposal_hash TEXT,
            pattern_score REAL,
            pattern_compilation_id TEXT,
            compiled_binding_id TEXT,
            compiled_binding_hash TEXT,
            graph_features {json_type},
            difficulty_score REAL,
            answer_schema {json_type},
            question_intent TEXT,
            entity_ids {json_type} NOT NULL,
            metric_ids {json_type} NOT NULL,
            time_scope {json_type} NOT NULL,
            entity_scope {json_type} NOT NULL,
            source_fact_ids {json_type} NOT NULL,
            source_derived_ids {json_type} NOT NULL,
            source_document_ids {json_type} NOT NULL,
            raw_object_ids {json_type} NOT NULL,
            canonical_semantics {json_type} NOT NULL,
            derived_payload {json_type} NOT NULL,
            recomputed_payload {json_type} NOT NULL,
            answer_payload {json_type} NOT NULL,
            kg_path {json_type} NOT NULL,
            eligibility_status TEXT NOT NULL,
            rejection_reasons {json_type} NOT NULL,
            created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS qa_operation_plans (
            plan_id TEXT PRIMARY KEY,
            qa_build_id TEXT NOT NULL,
            candidate_id TEXT NOT NULL,
            pattern_id TEXT NOT NULL,
            pattern_version INTEGER NOT NULL,
            operator_dag {json_type} NOT NULL,
            input_bindings {json_type} NOT NULL,
            intermediate_results {json_type} NOT NULL,
            output_schema {json_type} NOT NULL,
            recompute_status TEXT NOT NULL,
            validation_errors {json_type} NOT NULL,
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
            evidence_node_ids {json_type} NOT NULL,
            evidence_edges {json_type} NOT NULL,
            evidence_components {json_type} NOT NULL,
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
        "CREATE INDEX IF NOT EXISTS idx_kg_nodes_build_type_source ON kg_nodes(kg_build_id, node_type, source_pk)",
        "CREATE INDEX IF NOT EXISTS idx_standardized_facts_qa_series ON standardized_facts(build_id, metric_id, entity_id, fiscal_year, fiscal_quarter, period_end)",
        "CREATE INDEX IF NOT EXISTS idx_qa_builds_kg_status ON qa_builds(kg_build_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_qa_mining_runs_kg_status ON qa_pattern_mining_runs(kg_build_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_qa_proposals_kg_status_score ON qa_pattern_proposals(kg_build_id, status, total_score)",
        "CREATE INDEX IF NOT EXISTS idx_qa_compilations_build_proposal ON qa_pattern_compilations(qa_build_id, proposal_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_qa_compiled_bindings_compilation ON qa_compiled_bindings(compilation_id, execution_status)",
        "CREATE INDEX IF NOT EXISTS idx_qa_graph_motifs_run_family ON qa_graph_motif_observations(mining_run_id, motif_family, status)",
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
            "mining_run_id": "TEXT",
            "template_manifest_hash": "TEXT",
            "pattern_manifest_hash": "TEXT",
            "operator_manifest_hash": "TEXT",
            "difficulty_policy_hash": "TEXT",
            "generator_version": "TEXT",
            "git_commit_sha": "TEXT",
            "split_policy_hash": "TEXT",
        },
        "qa_samples": {
            "template_id": "TEXT",
            "template_hash": "TEXT",
            "surface_form_id": "TEXT",
            "paraphrase_group_id": "TEXT",
            "linguistic_style": "TEXT",
            "graph_pattern_id": "TEXT",
            "operation_depth": "INTEGER",
        },
        "qa_candidates": {
            "derived_payload": "JSONB" if postgres else "TEXT",
            "recomputed_payload": "JSONB" if postgres else "TEXT",
            "pattern_id": "TEXT",
            "pattern_version": "INTEGER",
            "pattern_hash": "TEXT",
            "operation_plan_id": "TEXT",
            "operation_plan_hash": "TEXT",
            "mining_run_id": "TEXT",
            "pattern_proposal_id": "TEXT",
            "pattern_proposal_hash": "TEXT",
            "pattern_score": "REAL",
            "pattern_compilation_id": "TEXT",
            "compiled_binding_id": "TEXT",
            "compiled_binding_hash": "TEXT",
            "graph_features": "JSONB" if postgres else "TEXT",
            "difficulty_score": "REAL",
            "answer_schema": "JSONB" if postgres else "TEXT",
            "question_intent": "TEXT",
        },
        "qa_evidence_paths": {
            "evidence_node_ids": "JSONB" if postgres else "TEXT",
            "evidence_edges": "JSONB" if postgres else "TEXT",
            "evidence_components": "JSONB" if postgres else "TEXT",
        },
        "qa_graph_patterns": {
            "matcher": "TEXT",
            "pattern_hash": "TEXT",
        },
        "qa_pattern_proposals": {
            "proposal_semantic_id": "TEXT",
            "proposal_snapshot_id": "TEXT",
            "static_pattern_id": "TEXT",
            "binding_mode": "TEXT",
            "heldout_bindings": "JSONB" if postgres else "TEXT",
            "semantic_validation_results": "JSONB" if postgres else "TEXT",
            "operation_validation_results": "JSONB" if postgres else "TEXT",
            "lifecycle_events": "JSONB" if postgres else "TEXT",
            "semantic_constraint_pass_rate": "REAL",
            "operation_execution_pass_rate": "REAL",
            "example_binding_pass_rate": "REAL",
            "heldout_binding_pass_rate": "REAL",
            "static_pattern_overlap": "REAL",
            "binding_diversity_score": "REAL",
            "manual_review_status": "TEXT",
        },
        "qa_pattern_mining_runs": {
            "reviewed_at": "TIMESTAMPTZ" if postgres else "TEXT",
            "reviewed_by": "TEXT",
            "approved_at": "TIMESTAMPTZ" if postgres else "TEXT",
            "approved_by": "TEXT",
            "superseded_at": "TIMESTAMPTZ" if postgres else "TEXT",
            "superseded_by_run_id": "TEXT",
            "lifecycle_events": "JSONB" if postgres else "TEXT",
        },
        "standardized_facts": {
            "entity_scope_id": "TEXT",
            "financial_scope_type": "TEXT",
        },
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
    for statement in [
        "CREATE INDEX IF NOT EXISTS idx_standardized_facts_financial_scope ON standardized_facts(entity_scope_id, financial_scope_type)",
        "CREATE INDEX IF NOT EXISTS idx_qa_builds_mining_run ON qa_builds(mining_run_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_qa_proposals_semantic_snapshot ON qa_pattern_proposals(proposal_semantic_id, proposal_snapshot_id)",
        "CREATE INDEX IF NOT EXISTS idx_qa_patterns_family_active ON qa_graph_patterns(pattern_family, is_active)",
        "CREATE INDEX IF NOT EXISTS idx_qa_candidates_pattern ON qa_candidates(qa_build_id, pattern_id, eligibility_status)",
        "CREATE INDEX IF NOT EXISTS idx_qa_patterns_family_active ON qa_graph_patterns(pattern_family, is_active)",
        "CREATE INDEX IF NOT EXISTS idx_qa_mining_runs_kg_status ON qa_pattern_mining_runs(kg_build_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_qa_proposals_kg_status_score ON qa_pattern_proposals(kg_build_id, status, total_score)",
        "CREATE INDEX IF NOT EXISTS idx_qa_compilations_build_proposal ON qa_pattern_compilations(qa_build_id, proposal_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_qa_compiled_bindings_compilation ON qa_compiled_bindings(compilation_id, execution_status)",
        "CREATE INDEX IF NOT EXISTS idx_qa_graph_motifs_run_family ON qa_graph_motif_observations(mining_run_id, motif_family, status)",
        "CREATE INDEX IF NOT EXISTS idx_qa_candidates_pattern ON qa_candidates(qa_build_id, pattern_id, eligibility_status)",
        "CREATE INDEX IF NOT EXISTS idx_qa_candidates_proposal ON qa_candidates(qa_build_id, pattern_proposal_id, eligibility_status)",
        "CREATE INDEX IF NOT EXISTS idx_qa_plans_build_pattern ON qa_operation_plans(qa_build_id, pattern_id, recompute_status)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_qa_plans_candidate ON qa_operation_plans(candidate_id)",
    ]:
        db.execute(statement)
