from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from finraw.db.client import MetadataDB
from finraw.qa.finsearchcomp_alignment import (
    _contamination_report,
    _current_market,
    _generation_pipeline,
    _legacy_operations,
    _legacy_period_count,
    _question_completeness,
    align_qa_build_to_finsearchcomp,
    analyze_official_finsearchcomp,
    benchmark_task_difficulty_audit,
    classify_current_benchmark_task,
    freeze_finsearchcomp_dataset,
)
from finraw.qa.pipeline import (
    _benchmark_aligned_rubric,
    _validate_benchmark_output_contract,
)
from finraw.qa.schema import ensure_qa_schema
from finraw.qa.templates import template_for


def _official_rows() -> list[dict[str, str]]:
    labels = [
        "Time-Sensitive_Data_Fetching(Global)",
        "Time-Sensitive_Data_Fetching(Greater China)",
        "Simple_Historical_Lookup(Global)",
        "Simple_Historical_Lookup(Greater China)",
        "Complex_Historical_Investigation(Global)",
        "Complex_Historical_Investigation(Greater China)",
    ]
    prompts = [
        "What is the latest close price of IBM?",
        "今天上证指数收盘是多少？",
        "What was Apple's FY2023 revenue in million USD?",
        "2023年中国GDP是多少亿元？",
        "From 2020 to 2024, which year had the highest revenue and what was the value?",
        "在2020至2024年间，筛选收入增长为正的公司并排名前三。",
    ]
    return [
        {
            "prompt_id": f"prompt_{index}",
            "prompt": prompt,
            "response_reference": "100, 1% error allowed",
            "judge_prompt_template": "{prompt} {response_reference} {response}",
            "judge_system_prompt": "judge",
            "label": label,
        }
        for index, (label, prompt) in enumerate(zip(labels, prompts), start=1)
    ]


def _insert_candidate(
    db: MetadataDB,
    *,
    candidate_id: str,
    qa_build_id: str,
    subtype: str,
    pattern_id: str | None,
    entity_ids: list[str],
    metric_ids: list[str],
    time_scope: dict,
    source_id: str,
    graph_features: dict,
    answer_schema: dict,
) -> None:
    db.execute(
        """
        INSERT INTO qa_candidates (
            candidate_id, stable_candidate_id, qa_build_id, task_family,
            task_subtype, difficulty, pattern_id, entity_ids, metric_ids,
            time_scope, entity_scope, source_fact_ids, source_derived_ids,
            source_document_ids, raw_object_ids, canonical_semantics,
            derived_payload, recomputed_payload, answer_payload, kg_path,
            graph_features, answer_schema, eligibility_status, rejection_reasons
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            candidate_id,
            f"stable_{candidate_id}",
            qa_build_id,
            "financial_qa",
            subtype,
            "hard" if pattern_id else "easy",
            pattern_id,
            json.dumps(entity_ids),
            json.dumps(metric_ids),
            json.dumps(time_scope),
            json.dumps({}),
            json.dumps([]),
            json.dumps([]),
            json.dumps([]),
            json.dumps([]),
            json.dumps(
                {
                    "source_id": source_id,
                    "entity_type": "listed_company",
                    "frequency": "annual",
                }
            ),
            json.dumps({}),
            json.dumps({}),
            json.dumps({"value": "1"}),
            json.dumps({}),
            json.dumps(graph_features),
            json.dumps(answer_schema),
            "eligible",
            json.dumps([]),
        ),
    )


def _insert_sample(
    db: MetadataDB,
    *,
    qa_id: str,
    qa_build_id: str,
    candidate_id: str,
    subtype: str,
    question: str,
    answer_type: str,
) -> None:
    db.execute(
        """
        INSERT INTO qa_samples (
            qa_id, stable_qa_id, qa_group_id, semantic_cluster_id,
            qa_build_id, candidate_id, task_family, task_subtype,
            difficulty, language, question, canonical_question, answer_type,
            answer_value, answer_text, unit, currency, rubric,
            source_metadata, generation_method, validation_status, split
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            qa_id,
            f"stable_{qa_id}",
            f"group_{qa_id}",
            f"cluster_{qa_id}",
            qa_build_id,
            candidate_id,
            "financial_qa",
            subtype,
            "hard" if "rank" in subtype else "easy",
            "en",
            question,
            question,
            answer_type,
            json.dumps({"value": "1"}),
            "1 million USD",
            "million USD",
            "USD",
            json.dumps(
                {
                    "match_type": "numeric_tolerance",
                    "relative_tolerance": "0.01",
                }
            ),
            json.dumps({}),
            "deterministic_template",
            "passed",
            "train",
        ),
    )


def test_finsearchcomp_freeze_analyze_and_current_alignment(tmp_path: Path):
    raw_path = tmp_path / "official.json"
    raw_path.write_text(json.dumps(_official_rows()), encoding="utf-8")
    frozen_dir = tmp_path / "frozen"
    freeze = freeze_finsearchcomp_dataset(
        str(raw_path), str(frozen_dir), expected_sha256=None
    )

    assert freeze["row_count"] == 6
    assert freeze["usage"] == "evaluation_only"
    assert (frozen_dir / "SHA256SUMS").exists()
    frozen_manifest = [
        json.loads(line)
        for line in (frozen_dir / "official_evaluation_manifest.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert all("official_item_id" in row for row in frozen_manifest)

    analysis_dir = tmp_path / "analysis"
    stats = analyze_official_finsearchcomp(
        str(frozen_dir / "finsearchcomp_v1.parquet"), str(analysis_dir)
    )

    assert stats["task_distribution"] == {"T1": 2, "T2": 2, "T3": 2}
    assert stats["viewer_only_or_absent_fields"]["ground_truth"] == (
        "not_present_in_frozen_raw_json"
    )
    official_taxonomy = pd.read_parquet(analysis_dir / "item_taxonomy.parquet")
    assert set(official_taxonomy["benchmark_task"]) == {"T1", "T2", "T3"}
    assert (analysis_dir / "official_statistics.xlsx").exists()

    db = MetadataDB(str(tmp_path / "qa.db"))
    db.init_schema()
    ensure_qa_schema(db)
    db.execute(
        "INSERT INTO qa_builds (qa_build_id, kg_build_id, graph_schema_version, status) VALUES (?, ?, ?, ?)",
        ("qa_build", "kg_build", "kg.v1", "ready"),
    )
    _insert_candidate(
        db,
        candidate_id="candidate_t2",
        qa_build_id="qa_build",
        subtype="single_fact",
        pattern_id=None,
        entity_ids=["AAPL_US"],
        metric_ids=["revenue"],
        time_scope={
            "fiscal_year": 2023,
            "basis": "fiscal_year",
            "start_year": "2020 Q1",
            "end_year": "2020 Q4",
            "frequency": "quarterly",
        },
        source_id="sec_companyfacts",
        graph_features={"entity_count": 1, "period_count": 1},
        answer_schema={"type": "numeric"},
    )
    _insert_sample(
        db,
        qa_id="qa_t2",
        qa_build_id="qa_build",
        candidate_id="candidate_t2",
        subtype="single_fact",
        question="What was Apple's FY2023 revenue in million USD?",
        answer_type="numeric",
    )
    _insert_candidate(
        db,
        candidate_id="candidate_t3",
        qa_build_id="qa_build",
        subtype="filter_then_rank",
        pattern_id="industry_growth_filter_then_margin_rank",
        entity_ids=["A_US", "B_US", "C_US"],
        metric_ids=["revenue", "net_margin"],
        time_scope={"fiscal_year": 2023, "basis": "fiscal_year"},
        source_id="sec_companyfacts",
        graph_features={
            "entity_count": 3,
            "period_count": 2,
            "operation_depth": 2,
            "scope_size": 3,
        },
        answer_schema={"type": "ranked_table"},
    )
    _insert_sample(
        db,
        qa_id="qa_t3",
        qa_build_id="qa_build",
        candidate_id="candidate_t3",
        subtype="filter_then_rank",
        question=(
            "Among the covered companies in FY2023, filter those with positive "
            "revenue growth and rank the top 3 by net margin."
        ),
        answer_type="ranked_table",
    )
    db.execute(
        """
        INSERT INTO qa_operation_plans (
            plan_id, qa_build_id, candidate_id, pattern_id, pattern_version,
            operator_dag, input_bindings, intermediate_results, output_schema,
            recompute_status, validation_errors
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "plan_t3",
            "qa_build",
            "candidate_t3",
            "industry_growth_filter_then_margin_rank",
            1,
            json.dumps(
                {
                    "operators": [
                        {"step_id": "filter", "operator": "filter"},
                        {"step_id": "rank", "operator": "rank"},
                    ]
                }
            ),
            json.dumps({}),
            json.dumps({}),
            json.dumps({}),
            "passed",
            json.dumps([]),
        ),
    )

    output_dir = tmp_path / "alignment"
    report = align_qa_build_to_finsearchcomp(
        db,
        "qa_build",
        str(analysis_dir / "item_taxonomy.parquet"),
        str(output_dir),
        target_t2_count=20,
        target_t3_count=10,
    )

    assert report["current_task_counts"] == {"T2": 1, "T3": 1}
    assert report["contamination"]["exact_match_count"] == 1
    assert report["contamination"]["blocked_qa_count"] == 1
    assert report["contamination"]["training_release_gate"] == "failed"
    assert (output_dir / "contamination_manual_review.jsonl").exists()
    assert (output_dir / "contamination_exclusion_manifest.jsonl").exists()
    assert report["execution_quality"]["verifier_pass_rate"] == 1.0
    cross_audit = report["benchmark_task_difficulty_audit"]
    assert cross_audit["matrix"]["T2"]["easy"] == 1
    assert cross_audit["matrix"]["T3"]["hard"] == 1
    assert cross_audit["status"] == "passed"
    assert (output_dir / "benchmark_task_difficulty_matrix.csv").exists()
    assert (
        db.fetchone(
            "SELECT COUNT(*) AS c FROM qa_distribution_labels WHERE qa_build_id = ?",
            ("qa_build",),
        )["c"]
        == 2
    )
    labels = pd.read_parquet(output_dir / "current_qa_taxonomy.parquet")
    assert set(labels["generation_pipeline"]) == {"fact_qa", "static_graph_pattern"}
    assert (output_dir / "gap_manifest.json").exists()
    assert (output_dir / "agent_input_manifest.jsonl").exists()
    assert (output_dir / "hidden_gold_manifest.jsonl").exists()
    db.close()


def test_greater_china_macro_entities_are_classified_without_cninfo():
    assert _current_market(["worldbank_indicators"], ["CHN_COUNTRY"]) == (
        "greater_china"
    )
    assert (
        _current_market(["worldbank_indicators"], ["HKG_COUNTRY", "MAC_COUNTRY"])
        == "greater_china"
    )
    assert _current_market(["worldbank_indicators"], ["USA_COUNTRY"]) == "global"


def test_greater_china_exchange_sources_and_entities_are_classified():
    assert _current_market(["bse_disclosures"], ["920010_BSE"]) == "greater_china"
    assert _current_market(["hkex_disclosures"], ["02318_HKEX"]) == "greater_china"
    assert _current_market(["sse_market_statistics"], ["SSE_MARKET"]) == "greater_china"


def test_alignment_completeness_accepts_localized_chinese_output_contract():
    result = _question_completeness(
        "公司在2024财年的收入是多少？请以百万元人民币为单位，数值保留2位小数。",
        unit="million CNY",
        currency="CNY",
        time_scope={"basis": "fiscal_year", "fiscal_year": 2024},
        benchmark_task="T2",
    )
    assert all(result.values())


def test_alignment_completeness_treats_precision_as_applicability_aware():
    result = _question_completeness(
        "请使用完整表格并保持要求的顺序。",
        unit="",
        currency="",
        time_scope={},
        benchmark_task="T3",
        precision_required=False,
    )
    assert result["precision_explicit"] is True


def test_typed_walk_pipeline_is_classified_from_task_subtype():
    assert (
        _generation_pipeline(
            {
                "task_subtype": "walk_scope_filter_rank_followup",
                "pattern_id": "mined_pattern_1",
                "pattern_proposal_id": "proposal_1",
            }
        )
        == "typed_edge_walk"
    )


def test_chinese_template_and_benchmark_output_contract_are_fail_closed():
    template = template_for("single_fact", "period_flow", "candidate_1", language="zh")
    assert template["language"] == "zh"
    assert "多少" in template["template_text"]

    policy = {
        "benchmark_alignment": {
            "enabled": True,
            "decimal_places": 2,
            "explicit_unit": True,
            "explicit_precision": True,
            "explicit_output_format": True,
        }
    }
    rubric = _benchmark_aligned_rubric(
        {"match_type": "numeric_tolerance"},
        policy,
        {"value": "1", "unit": "million USD", "currency": "USD"},
        "numeric",
    )
    valid = _validate_benchmark_output_contract(
        {
            "question": "请以million USD为单位作答，数值保留2位小数。",
            "rubric": rubric,
        }
    )
    assert valid["passed"]

    invalid = _validate_benchmark_output_contract(
        {
            "question": "请以million USD为单位作答。",
            "rubric": rubric,
        }
    )
    assert not invalid["passed"]
    assert "requested_precision_missing" in invalid["errors"]


def test_chinese_output_contract_accepts_localized_unit_and_currency_aliases():
    cases = [
        ("请以百万元人民币为单位，数值保留2位小数。", "million CNY", "CNY"),
        ("请以人民币元/股为单位，数值保留2位小数。", "CNY_per_share", "CNY"),
        ("请以百万港元为单位，数值保留2位小数。", "million HKD", "HKD"),
        ("请以百分比为单位，数值保留2位小数。", "percent", ""),
    ]
    for question, unit, currency in cases:
        result = _validate_benchmark_output_contract(
            {
                "question": question,
                "rubric": {
                    "benchmark_alignment": "finsearchcomp",
                    "unit_must_match": True,
                    "requested_unit": unit,
                    "requested_currency": currency,
                    "precision_must_match": True,
                    "requested_decimal_places": 2,
                    "complete_output_required": False,
                },
            }
        )
        assert result["passed"], (question, result)


def test_chinese_output_contract_rejects_wrong_localized_currency():
    result = _validate_benchmark_output_contract(
        {
            "question": "请以百万港元为单位，数值保留2位小数。",
            "rubric": {
                "benchmark_alignment": "finsearchcomp",
                "unit_must_match": True,
                "requested_unit": "million CNY",
                "requested_currency": "CNY",
                "precision_must_match": True,
                "requested_decimal_places": 2,
                "complete_output_required": False,
            },
        }
    )
    assert not result["passed"]
    assert "requested_unit_missing" in result["errors"]
    assert "requested_currency_missing" in result["errors"]


def test_long_window_extrema_are_structurally_multi_period():
    row = {"source_fact_ids": [f"fact_{index}" for index in range(5)]}

    assert _legacy_period_count("multi_year_argmax", row) == 5
    assert _legacy_operations("multi_year_argmax") == [
        "lookup",
        "temporal_extreme",
    ]


def test_benchmark_task_classifier_does_not_treat_entity_count_alone_as_t3():
    task, reasons = classify_current_benchmark_task(
        period_count=1,
        entity_count=2,
        reasoning_operation_depth=1,
        source_count=1,
        scope_complete=False,
        answer_type="numeric",
    )
    assert task == "T2"
    assert reasons == []

    task, reasons = classify_current_benchmark_task(
        period_count=2,
        entity_count=2,
        reasoning_operation_depth=1,
        source_count=1,
        scope_complete=False,
        answer_type="comparison",
    )
    assert task == "T3"
    assert reasons == ["multi_entity_multi_period"]


def test_benchmark_task_difficulty_audit_flags_cross_distribution_anomalies():
    rows = [
        {
            "benchmark_task": "T3",
            "difficulty": "easy",
            "generation_pipeline": "fact_qa",
            "classification_reasons": ["period_count>=3"],
        }
        for _ in range(4)
    ]
    rows += [
        {
            "benchmark_task": "T3",
            "difficulty": "hard",
            "generation_pipeline": "automatic_pattern_mining",
            "classification_reasons": ["reasoning_operation_depth>=2"],
        }
    ]
    rows += [
        {
            "benchmark_task": "T2",
            "difficulty": "research",
            "generation_pipeline": "typed_edge_walk",
            "classification_reasons": ["fixed_historical_low_depth"],
        },
        {
            "benchmark_task": "T2",
            "difficulty": "easy",
            "generation_pipeline": "fact_qa",
            "classification_reasons": ["fixed_historical_low_depth"],
        },
    ]
    audit = benchmark_task_difficulty_audit(rows)
    assert audit["matrix"]["T3"]["easy"] == 4
    assert audit["t3_easy_ratio"] == 0.8
    assert audit["t2_expert_research_ratio"] == 0.5
    assert audit["t3_hard_or_higher_ratio"] == 0.2
    assert audit["status"] == "review_required"
    assert len(audit["failures"]) == 3
    assert audit["t3_easy_pipeline_counts"] == {"fact_qa": 4}


def test_alignment_difficulty_schema_migrates_before_index_creation(tmp_path: Path):
    db = MetadataDB(str(tmp_path / "legacy.sqlite"))
    db.init_schema()
    db.execute("DROP TABLE qa_distribution_labels")
    db.execute(
        "CREATE TABLE qa_distribution_labels ("
        "alignment_id TEXT PRIMARY KEY, qa_build_id TEXT NOT NULL, "
        "benchmark_task TEXT NOT NULL, market_subset TEXT NOT NULL)"
    )
    ensure_qa_schema(db)
    columns = {
        row["name"] for row in db.fetchall("PRAGMA table_info(qa_distribution_labels)")
    }
    assert "difficulty" in columns
    indexes = {
        row["name"] for row in db.fetchall("PRAGMA index_list(qa_distribution_labels)")
    }
    assert "idx_qa_distribution_build_task_difficulty" in indexes
    db.close()


def test_contamination_detects_company_and_year_substitution_without_exact_match():
    official = [
        {
            "item_id": "official_1",
            "prompt": "What was Apple's FY2023 revenue in million USD?",
            "normalized_prompt_sha256": "official_exact_hash",
            "metric_families": ["revenue"],
            "operation_families": ["lookup"],
            "answer_type": "numeric",
            "period_count": 1,
            "time_basis": "fiscal_period",
            "frequency": "annual",
        }
    ]
    current = [
        {
            "qa_id": "qa_substituted",
            "question": "What was Microsoft's FY2024 revenue in million USD?",
            "normalized_question_sha256": "different_exact_hash",
            "metric_families": ["revenue"],
            "operation_families": ["lookup"],
            "answer_type": "numeric",
            "period_count": 1,
            "time_basis": "fiscal_period",
            "frequency": "annual",
        }
    ]

    report = _contamination_report(official, current)

    assert report["exact_match_count"] == 0
    assert report["question_skeleton_match_count"] == 1
    assert report["slot_normalized_match_count"] == 1
    assert report["blocked_qa_ids"] == ["qa_substituted"]
    assert report["passed"] is False


def test_operation_program_match_alone_is_not_treated_as_contamination():
    official = [
        {
            "item_id": "official_1",
            "prompt": "What was Apple's FY2023 revenue?",
            "normalized_prompt_sha256": "official_hash",
            "metric_families": ["revenue"],
            "operation_families": ["lookup"],
            "answer_type": "numeric",
            "period_count": 1,
            "time_basis": "fiscal_period",
            "frequency": "annual",
        }
    ]
    current = [
        {
            "qa_id": "qa_unrelated_lookup",
            "question": "Report the unemployment rate for Germany in January 2010.",
            "normalized_question_sha256": "current_hash",
            "metric_families": ["employment"],
            "operation_families": ["lookup"],
            "answer_type": "numeric",
            "period_count": 1,
            "time_basis": "calendar_period",
            "frequency": "monthly",
        }
    ]

    report = _contamination_report(official, current)

    assert report["operation_program_match_count"] == 1
    assert report["blocked_qa_count"] == 0
    assert report["passed"] is True


def test_synonymous_benchmark_paraphrase_enters_manual_review_queue():
    official = [
        {
            "item_id": "official_extreme",
            "prompt": (
                "From 2020 to 2024, which year had the highest revenue "
                "and what was the value?"
            ),
            "normalized_prompt_sha256": "official_extreme_hash",
            "metric_families": ["revenue"],
            "operation_families": ["argmax", "lookup"],
            "answer_type": "period_and_value",
            "period_count": 5,
            "time_basis": "fiscal_period",
            "frequency": "annual",
        }
    ]
    current = [
        {
            "qa_id": "qa_paraphrase",
            "question": (
                "Identify the fiscal year between 2019 and 2023 when sales "
                "peaked, and report the corresponding amount."
            ),
            "normalized_question_sha256": "different_hash",
            "metric_families": ["revenue"],
            "operation_families": ["argmax", "lookup"],
            "answer_type": "period_and_value",
            "period_count": 5,
            "time_basis": "fiscal_period",
            "frequency": "annual",
        }
    ]

    report = _contamination_report(
        official,
        current,
        policy={"minimum_calibration_review_pairs": 0},
    )

    assert report["exact_match_count"] == 0
    assert report["embedding_review_count"] == 1
    assert report["manual_review_qa_count"] == 1
    assert report["training_release_gate"] == "pending_manual_review"
    assert report["training_release_ready"] is False
