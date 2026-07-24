from __future__ import annotations

from finraw.db.client import DBProtocol


def ensure_evaluation_schema(db: DBProtocol) -> None:
    postgres = db.__class__.__name__ == "PostgresMetadataDB"
    json_type = "JSONB" if postgres else "TEXT"
    timestamp_type = "TIMESTAMPTZ" if postgres else "TEXT"
    bool_type = "BOOLEAN" if postgres else "INTEGER"
    false_literal = "FALSE" if postgres else "0"
    statements = [
        f"""
        CREATE TABLE IF NOT EXISTS qa_evaluation_runs (
            evaluation_run_id TEXT PRIMARY KEY,
            qa_build_id TEXT NOT NULL,
            rubric_version TEXT NOT NULL,
            rubric_hash TEXT NOT NULL,
            evaluation_config_hash TEXT NOT NULL,
            judge_config_hash TEXT NOT NULL,
            judge_manifest {json_type} NOT NULL,
            sample_manifest {json_type} NOT NULL,
            sample_manifest_hash TEXT NOT NULL,
            calibration_version TEXT,
            evaluation_mode TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at {timestamp_type},
            completed_at {timestamp_type},
            git_commit_sha TEXT,
            notes {json_type} NOT NULL
        )
        """,
        f"""
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
            scores {json_type} NOT NULL,
            fatal_flags {json_type} NOT NULL,
            issue_codes {json_type} NOT NULL,
            confidence REAL,
            brief_justification {json_type} NOT NULL,
            telemetry {json_type} NOT NULL,
            status TEXT NOT NULL,
            error_message TEXT,
            created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(evaluation_run_id, qa_id, judge_role)
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS qa_evaluation_items (
            evaluation_item_id TEXT PRIMARY KEY,
            evaluation_run_id TEXT NOT NULL,
            qa_id TEXT NOT NULL,
            deterministic_gate_status TEXT NOT NULL,
            deterministic_gate_reasons {json_type} NOT NULL,
            dimension_scores {json_type} NOT NULL,
            subjective_quality_score REAL,
            standalone_financial_value_score REAL,
            dataset_role_value_score REAL NOT NULL,
            coverage_contributions {json_type} NOT NULL,
            dataset_role_components {json_type} NOT NULL,
            judge_disagreement {json_type} NOT NULL,
            judge_confidence REAL,
            fatal_flags {json_type} NOT NULL,
            confirmed_fatal_flags {json_type} NOT NULL,
            issue_codes {json_type} NOT NULL,
            decision TEXT NOT NULL,
            decision_reasons {json_type} NOT NULL,
            created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(evaluation_run_id, qa_id)
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS qa_human_reviews (
            human_review_id TEXT PRIMARY KEY,
            evaluation_run_id TEXT NOT NULL,
            qa_id TEXT NOT NULL,
            reviewer_id TEXT NOT NULL,
            rubric_version TEXT NOT NULL,
            dimension_scores {json_type} NOT NULL,
            fatal_flags {json_type} NOT NULL,
            decision TEXT NOT NULL,
            reason_codes {json_type} NOT NULL,
            reviewed_at {timestamp_type} NOT NULL,
            UNIQUE(evaluation_run_id, qa_id, reviewer_id)
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS qa_perturbation_cases (
            perturbation_id TEXT PRIMARY KEY,
            source_qa_id TEXT NOT NULL,
            perturbed_question TEXT NOT NULL,
            perturbation_type TEXT NOT NULL,
            expected_affected_dimensions {json_type} NOT NULL,
            expected_fatal_flags {json_type} NOT NULL,
            mutation_manifest {json_type} NOT NULL,
            status TEXT NOT NULL,
            created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS qa_quality_releases (
            quality_release_id TEXT PRIMARY KEY,
            qa_build_id TEXT NOT NULL,
            evaluation_run_id TEXT NOT NULL,
            selection_policy_version TEXT NOT NULL,
            target_size BIGINT NOT NULL,
            distribution_contract {json_type} NOT NULL,
            quality_thresholds {json_type} NOT NULL,
            member_manifest_hash TEXT,
            status TEXT NOT NULL,
            created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS qa_quality_release_members (
            release_member_id TEXT PRIMARY KEY,
            quality_release_id TEXT NOT NULL,
            qa_id TEXT NOT NULL,
            selection_score REAL NOT NULL,
            subjective_score REAL NOT NULL,
            dataset_role_score REAL NOT NULL,
            novelty_score REAL NOT NULL,
            selection_stratum TEXT NOT NULL,
            selection_reason {json_type} NOT NULL,
            is_selected {bool_type} DEFAULT {false_literal},
            UNIQUE(quality_release_id, qa_id)
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS qa_empirical_runs (
            empirical_run_id TEXT PRIMARY KEY,
            qa_build_ids {json_type} NOT NULL,
            evaluation_mode TEXT NOT NULL,
            model_manifest {json_type} NOT NULL,
            sample_manifest {json_type} NOT NULL,
            config_hash TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at {timestamp_type},
            completed_at {timestamp_type},
            notes {json_type} NOT NULL
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS qa_empirical_model_trials (
            trial_id TEXT PRIMARY KEY,
            empirical_run_id TEXT NOT NULL,
            qa_build_id TEXT NOT NULL,
            qa_id TEXT NOT NULL,
            model_role TEXT NOT NULL,
            provider TEXT,
            requested_model TEXT NOT NULL,
            response_model TEXT,
            answer_text TEXT NOT NULL,
            answer_payload {json_type} NOT NULL,
            match_status TEXT NOT NULL,
            match_details {json_type} NOT NULL,
            prompt_hash TEXT NOT NULL,
            response_hash TEXT,
            telemetry {json_type} NOT NULL,
            status TEXT NOT NULL,
            error_message TEXT,
            created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(empirical_run_id, qa_id, model_role)
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_qaeval_runs_build_status ON qa_evaluation_runs(qa_build_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_qaeval_calls_run_qa ON qa_judge_calls(evaluation_run_id, qa_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_qaeval_items_run_decision ON qa_evaluation_items(evaluation_run_id, decision)",
        "CREATE INDEX IF NOT EXISTS idx_qaeval_reviews_run_qa ON qa_human_reviews(evaluation_run_id, qa_id)",
        "CREATE INDEX IF NOT EXISTS idx_qaeval_release_run ON qa_quality_releases(evaluation_run_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_qaempirical_runs_status ON qa_empirical_runs(status, started_at)",
        "CREATE INDEX IF NOT EXISTS idx_qaempirical_trials_run_model ON qa_empirical_model_trials(empirical_run_id, model_role, match_status)",
    ]
    for statement in statements:
        db.execute(statement)
