from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from finraw.db.client import MetadataDB
from finraw.llm_client import JsonCompletion
from finraw.qa.evaluation.contracts import JudgeContractError, normalize_judge_payload
from finraw.qa.evaluation.input_views import load_evaluation_bundles
from finraw.qa.evaluation.empirical import (
    _contract_repair_prompt,
    _stratified_sample,
    match_empirical_answer,
    match_numeric_answer,
    run_empirical_model_evaluation,
)
from finraw.qa.evaluation.pipeline import (
    adjudicate_quality_run,
    init_quality_evaluation,
    quality_evaluation_report,
    run_quality_evaluation,
)
from finraw.qa.schema import ensure_qa_schema


def test_quality_evaluation_dual_judge_and_report(tmp_path: Path) -> None:
    db = _db_with_sample(tmp_path, failed_l0=False)
    config = _config()
    initialized = init_quality_evaluation(db, config, "qa_build_eval")

    views: list[dict[str, Any]] = []

    def fake_judge(
        role: str, view: dict[str, Any], rubric: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        views.append(view)
        score = 4 if role == "surface_financial_analyst" else 5
        return _judge_payload(score), {
            "provider": "fixture",
            "model_requested": "fixture-model",
            "response_model": "fixture-model",
            "input_view_hash": f"view-{role}",
            "prompt_hash": f"prompt-{role}",
            "response_hash": f"response-{role}",
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        }

    output_dir = tmp_path / "report"
    report = run_quality_evaluation(
        db,
        initialized["evaluation_run_id"],
        output_dir=str(output_dir),
        judge_function=fake_judge,
    )

    assert report["population"]["sample_count"] == 1
    assert report["population"]["judge_call_success_count"] == 2
    assert report["decision_counts"] == {"accepted": 1}
    assert report["subjective_quality"]["mean"] == pytest.approx(87.5)
    assert report["telemetry"]["total_tokens"] == 300
    assert all("answer_value" not in json.dumps(view) for view in views)
    assert all("answer_payload" not in json.dumps(view) for view in views)
    assert (output_dir / "qa_quality_evaluation_report.json").exists()
    assert (output_dir / "qa_evaluation_items.jsonl").exists()

    stored = db.fetchone(
        "SELECT decision, subjective_quality_score FROM qa_evaluation_items "
        "WHERE evaluation_run_id = ?",
        (initialized["evaluation_run_id"],),
    )
    assert stored["decision"] == "accepted"
    assert stored["subjective_quality_score"] == pytest.approx(87.5)
    db.close()


def test_l0_failure_vetoes_judges(tmp_path: Path) -> None:
    db = _db_with_sample(tmp_path, failed_l0=True)
    initialized = init_quality_evaluation(db, _config(), "qa_build_eval")
    called = False

    def should_not_run(*args: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        nonlocal called
        called = True
        return _judge_payload(5), {}

    report = run_quality_evaluation(
        db,
        initialized["evaluation_run_id"],
        judge_function=should_not_run,
    )

    assert called is False
    assert report["population"]["judge_call_count"] == 0
    assert report["decision_counts"] == {"rejected_deterministic": 1}
    item = db.fetchone(
        "SELECT deterministic_gate_reasons FROM qa_evaluation_items "
        "WHERE evaluation_run_id = ?",
        (initialized["evaluation_run_id"],),
    )
    assert "independent_recompute" in item["deterministic_gate_reasons"]
    db.close()


def test_surface_and_grounded_views_do_not_expose_gold_answer(tmp_path: Path) -> None:
    db = _db_with_sample(tmp_path, failed_l0=False)
    bundle = load_evaluation_bundles(db, "qa_build_eval")[0]

    serialized = json.dumps(
        {"surface": bundle["surface_view"], "grounded": bundle["grounded_view"]}
    )
    assert "383285" not in serialized
    assert "fact_secret" not in serialized
    assert bundle["grounded_view"]["operation_summary"] == [
        {"operator": "lookup", "semantic_parameters": {}}
    ]
    db.close()


def test_judge_contract_is_fail_closed() -> None:
    payload = _judge_payload(4)
    payload["scores"].pop("financial_semantic_validity")
    with pytest.raises(JudgeContractError, match="Score dimensions mismatch"):
        normalize_judge_payload(payload)

    payload = _judge_payload(4)
    payload["fatal_flags"] = ["invented_fatal_flag"]
    with pytest.raises(JudgeContractError, match="Unknown fatal flags"):
        normalize_judge_payload(payload)


def test_report_can_be_replayed_from_persisted_results(tmp_path: Path) -> None:
    db = _db_with_sample(tmp_path, failed_l0=False)
    initialized = init_quality_evaluation(db, _config(), "qa_build_eval")
    run_quality_evaluation(
        db,
        initialized["evaluation_run_id"],
        judge_function=lambda role, view, rubric: (_judge_payload(4), {}),
    )
    report = quality_evaluation_report(db, initialized["evaluation_run_id"])
    assert report["evaluation_run_id"] == initialized["evaluation_run_id"]
    assert report["slices"]["benchmark_task"]["T2"]["sample_count"] == 1
    db.close()


def _config() -> dict[str, Any]:
    return {
        "qa": {
            "quality_evaluation": {
                "enabled": True,
                "evaluation_mode": "advisory",
                "rubric_version": "financial_qa_quality.v1",
                "maximum_concurrency": 2,
                "judge_routing": {
                    "base_judges": [
                        "surface_financial_analyst",
                        "grounded_qa_auditor",
                    ],
                    "adjudicator": "adversarial_reviewer",
                    "total_score_disagreement_threshold": 30,
                    "dimension_disagreement_threshold": 2,
                    "minimum_confidence": 0.7,
                },
                "decision_thresholds": {
                    "accepted": 80,
                    "coverage_acceptance": 70,
                    "manual_review": 60,
                },
                "calibration": {
                    "calibration_set_version": "qa_quality_calibration.v1",
                    "thresholds_are_calibrated": False,
                },
                "llm": {},
            }
        }
    }


def _judge_payload(score: int) -> dict[str, Any]:
    return {
        "rubric_version": "financial_qa_quality.v1",
        "scores": {
            "task_authenticity": score,
            "standalone_financial_value": score,
            "financial_semantic_validity": score,
            "clarity_unambiguity": score,
            "reasoning_necessity": score,
            "evidence_scope_fit": score,
            "answer_rubric_fit": score,
            "language_quality": score,
        },
        "fatal_flags": [],
        "issue_codes": [],
        "confidence": 0.9,
        "brief_justification": {
            "financial_value": "Useful historical verification task.",
            "main_weakness": "None material.",
        },
    }


def _db_with_sample(tmp_path: Path, *, failed_l0: bool) -> MetadataDB:
    db = MetadataDB(str(tmp_path / "metadata.sqlite3"))
    db.init_schema()
    ensure_qa_schema(db)
    db.execute(
        "INSERT INTO qa_builds (qa_build_id, kg_build_id, graph_schema_version, "
        "status, quality_status) VALUES (?, ?, ?, ?, ?)",
        ("qa_build_eval", "kg_eval", "v3", "complete", "passed"),
    )
    db.execute(
        """
        INSERT INTO qa_candidates (
            candidate_id, stable_candidate_id, qa_build_id, task_family,
            task_subtype, difficulty, entity_ids, metric_ids, time_scope,
            entity_scope, source_fact_ids, source_derived_ids,
            source_document_ids, raw_object_ids, canonical_semantics,
            derived_payload, recomputed_payload, answer_payload, kg_path,
            eligibility_status, rejection_reasons, answer_schema
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "candidate_eval",
            "stable_candidate_eval",
            "qa_build_eval",
            "fact_lookup",
            "single_fact",
            "easy",
            json.dumps(["AAPL_US"]),
            json.dumps(["revenue"]),
            json.dumps({"fiscal_year": 2023}),
            json.dumps({}),
            json.dumps(["fact_secret"]),
            json.dumps([]),
            json.dumps([]),
            json.dumps(["raw_secret"]),
            json.dumps(
                {
                    "entity_names": ["Apple"],
                    "metric_names": ["revenue"],
                    "time_scope": {"fiscal_year": 2023},
                }
            ),
            json.dumps({}),
            json.dumps({}),
            json.dumps({"value": "383285", "unit": "million USD"}),
            json.dumps({}),
            "eligible",
            json.dumps([]),
            json.dumps({"type": "numeric"}),
        ),
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
            "plan_eval",
            "qa_build_eval",
            "candidate_eval",
            "single_fact",
            1,
            json.dumps(
                {"operators": [{"step_id": "lookup", "operator": "lookup"}]}
            ),
            json.dumps({}),
            json.dumps([]),
            json.dumps({"type": "numeric"}),
            "passed",
            json.dumps([]),
        ),
    )
    db.execute(
        """
        INSERT INTO qa_samples (
            qa_id, stable_qa_id, qa_group_id, semantic_cluster_id, qa_build_id,
            candidate_id, task_family, task_subtype, difficulty, language,
            question, canonical_question, answer_type, answer_value, answer_text,
            unit, currency, rubric, source_metadata, generation_method,
            validation_status, split
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "qa_eval",
            "stable_qa_eval",
            "group_eval",
            "cluster_eval",
            "qa_build_eval",
            "candidate_eval",
            "fact_lookup",
            "single_fact",
            "easy",
            "en",
            "What revenue did Apple report for fiscal 2023, in USD millions?",
            "What was Apple's revenue in fiscal 2023?",
            "numeric",
            json.dumps({"value": "383285"}),
            "383285 million USD",
            "million",
            "USD",
            json.dumps({"match_type": "numeric", "unit": "million USD"}),
            json.dumps({}),
            "controlled_template",
            "passed",
            "train",
        ),
    )
    db.execute(
        """
        INSERT INTO qa_distribution_labels (
            alignment_id, qa_id, qa_build_id, alignment_standard,
            alignment_version, benchmark_task, difficulty, market_subset,
            language, topic, subtopic, entity_type, metric_families,
            source_classes, time_basis, frequency, period_count,
            time_span_months, answer_type, operation_families,
            primary_operation_family, operation_depth, scope_size, rubric_type,
            generation_pipeline, structural_features, completeness_checks,
            classification_reasons, label_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "alignment_eval",
            "qa_eval",
            "qa_build_eval",
            "finsearchcomp",
            "1.2",
            "T2",
            "easy",
            "global",
            "en",
            "equity_fundamentals",
            "revenue",
            "company",
            json.dumps(["revenue"]),
            json.dumps(["official_filing"]),
            "fiscal_period",
            "annual",
            1,
            0,
            "numeric",
            json.dumps(["lookup"]),
            "lookup",
            1,
            1,
            "numeric",
            "fact_qa",
            json.dumps({}),
            json.dumps({}),
            json.dumps([]),
            "label_eval",
        ),
    )
    db.execute(
        "INSERT INTO qa_quality_checks (check_id, qa_id, qa_build_id, check_name, "
        "check_status) VALUES (?, ?, ?, ?, ?)",
        (
            "check_eval",
            "qa_eval",
            "qa_build_eval",
            "independent_recompute",
            "failed" if failed_l0 else "passed",
        ),
    )
    return db



def test_llm_secondary_review_replaces_pending_manual_step(tmp_path: Path) -> None:
    db = _db_with_sample(tmp_path, failed_l0=False)
    config = _config()
    quality = config["qa"]["quality_evaluation"]
    quality["calibration"]["required"] = False
    quality["calibration"]["replacement_mode"] = "llm_secondary_review"
    quality["judge_routing"]["secondary_review_scope"] = "all"
    initialized = init_quality_evaluation(db, config, "qa_build_eval")

    first = run_quality_evaluation(
        db,
        initialized["evaluation_run_id"],
        judge_function=lambda role, view, rubric: (_judge_payload(5), {}),
    )
    assert first["decision_counts"] == {"llm_secondary_review": 1}

    final = adjudicate_quality_run(
        db,
        initialized["evaluation_run_id"],
        judge_function=lambda role, view, rubric: (_judge_payload(5), {}),
    )
    assert final["decision_counts"] == {"accepted": 1}
    assert final["population"]["judge_call_success_count"] == 3
    assert "temporarily disabled" in final["policy_note"]
    db.close()


def test_numeric_l3_match_uses_display_tolerance() -> None:
    matched, details = match_numeric_answer(
        {"value": "74.00087773", "unit": "million CNY"},
        {"value": "74.00", "unit": "million CNY", "currency": "CNY"},
        {
            "target_value": "74.00087773",
            "requested_unit": "million CNY",
            "unit_must_match": True,
            "requested_currency": "CNY",
            "display_absolute_tolerance": "0.005",
        },
    )
    assert matched is True
    assert details["tolerance"] == "0.005"


def test_l3_dual_model_trials_are_scored_by_gold(tmp_path: Path) -> None:
    db = _db_with_sample(tmp_path, failed_l0=False)
    config = _config()
    quality = config["qa"]["quality_evaluation"]
    quality["llm"] = {
        "provider": "fixture",
        "endpoint": "https://fixture.invalid/v1/chat/completions",
        "model": "fixture",
        "api_key_env": "IGNORED",
    }
    quality["empirical_evaluation"] = {
        "enabled": True,
        "mode": "evidence_given",
        "maximum_concurrency": 2,
        "supported_answer_types": ["numeric"],
        "models": [
            {"model_role": "pro", "model": "deepseek-v4-pro"},
            {"model_role": "flash", "model": "deepseek-v4-flash"},
        ],
    }

    class FakeClient:
        def __init__(self, model_config: dict[str, Any]):
            self.model = model_config["model"]

        def complete_json(self, prompt: str, *, temperature: float) -> JsonCompletion:
            assert "383285" not in prompt
            return JsonCompletion(
                {
                    "answer_text": "383285 million USD",
                    "answer_payload": {
                        "value": "383285",
                        "unit": "million USD",
                        "currency": "USD",
                    },
                },
                {
                    "provider": "fixture",
                    "model_selected": self.model,
                    "response_model": self.model,
                    "total_tokens": 10,
                    "model_fallback_used": False,
                },
            )

    report = run_empirical_model_evaluation(
        db,
        config,
        ["qa_build_eval"],
        limit=1,
        output_dir=str(tmp_path / "empirical"),
        client_factory=FakeClient,
    )
    assert report["trial_count"] == 2
    assert report["model_results"]["pro"]["answer_pass_rate"] == 1.0
    assert report["model_results"]["flash"]["answer_pass_rate"] == 1.0
    assert report["scoring_policy"]["model_as_judge"] is False
    assert (tmp_path / "empirical" / "qa_empirical_report.json").exists()
    db.close()



def test_l3_small_sample_balances_markets_before_substrata() -> None:
    bundles = []
    for market in ("global", "greater_china"):
        for index in range(6):
            bundles.append(
                {
                    "qa_id": f"{market}_{index}",
                    "distribution_label": {
                        "market_subset": market,
                        "benchmark_task": "T2" if index % 2 == 0 else "T3",
                    },
                    "sample": {
                        "task_subtype": f"task_{index}",
                        "language": "en" if market == "global" else "zh",
                    },
                }
            )

    selected = _stratified_sample(bundles, 6, "balanced-seed")
    counts = {
        market: sum(
            row["distribution_label"]["market_subset"] == market
            for row in selected
        )
        for market in ("global", "greater_china")
    }
    assert counts == {"global": 3, "greater_china": 3}
    for market in ("global", "greater_china"):
        assert {
            row["distribution_label"]["benchmark_task"]
            for row in selected
            if row["distribution_label"]["market_subset"] == market
        } == {"T2", "T3"}



@pytest.mark.parametrize(
    ("answer_type", "expected", "observed", "rubric"),
    [
        (
            "comparison",
            {
                "winner_id": "A",
                "relation": "greater",
                "difference": "10.004",
                "rows": [
                    {"id": "A", "value": "20.004"},
                    {"id": "B", "value": "10"},
                ],
            },
            {
                "winner_id": "A",
                "relation": "greater",
                "difference": "10.00",
                "rows": [
                    {"id": "A", "value": "20.00"},
                    {"id": "B", "value": "10.00"},
                ],
                "unit": "million USD",
            },
            {
                "requested_unit": "million USD",
                "unit_must_match": True,
                "requested_decimal_places": 2,
            },
        ),
        (
            "period_and_value",
            {"result_period": 2023, "value": "99.996", "unit": "percent"},
            {"result_period": "2023", "value": "100.00", "unit": "percent"},
            {
                "target_period": 2023,
                "target_value": "99.996",
                "requested_unit": "percent",
                "unit_must_match": True,
                "requested_decimal_places": 2,
            },
        ),
        (
            "ranked_table",
            {"table": [{"rank": 1, "entity_id": "A", "value": "7.322"}]},
            {
                "table": [{"rank": 1, "entity_id": "A", "value": "7.32"}],
                "unit": "percent",
            },
            {
                "target_rows": [
                    {"rank": 1, "entity_id": "A", "value": "7.322"}
                ],
                "requested_unit": "percent",
                "unit_must_match": True,
                "requested_decimal_places": 2,
            },
        ),
        (
            "period_metric_provenance",
            {
                "result_period": 2024,
                "primary_value": "12",
                "secondary_value": "3.141",
                "raw_object_ids": ["raw_1"],
                "unit": "million CNY",
            },
            {
                "result_period": 2024,
                "primary_value": "12.00",
                "secondary_value": "3.14",
                "raw_object_ids": ["raw_1"],
                "unit": "million CNY",
            },
            {
                "target_period": 2024,
                "primary_value": "12",
                "secondary_value": "3.141",
                "requested_unit": "million CNY",
                "unit_must_match": True,
                "requested_decimal_places": 2,
            },
        ),
    ],
)
def test_l3_structured_answer_contracts(
    answer_type: str,
    expected: dict[str, Any],
    observed: dict[str, Any],
    rubric: dict[str, Any],
) -> None:
    matched, details = match_empirical_answer(
        answer_type, expected, observed, rubric
    )
    assert matched is True, details


def test_l3_table_contract_rejects_missing_scope_row() -> None:
    matched, details = match_empirical_answer(
        "screening_table",
        {"table": []},
        {
            "table": [
                {
                    "entity_id": "A",
                    "revenue_growth_pct": "10",
                    "net_margin_pct": "5",
                    "debt_ratio_pct": "30",
                }
            ],
            "unit": "percent",
        },
        {
            "target_rows": [
                {
                    "entity_id": "A",
                    "revenue_growth_pct": "10",
                    "net_margin_pct": "5",
                    "debt_ratio_pct": "30",
                },
                {
                    "entity_id": "B",
                    "revenue_growth_pct": "12",
                    "net_margin_pct": "6",
                    "debt_ratio_pct": "28",
                },
            ],
            "requested_unit": "percent",
            "unit_must_match": True,
        },
    )
    assert matched is False
    assert details["checks"]["table"] is False



def test_l3_comparison_rows_are_order_independent() -> None:
    matched, details = match_empirical_answer(
        "comparison",
        {
            "winner_id": "A",
            "relation": "greater",
            "difference": "10",
            "rows": [
                {"id": "B", "value": "10"},
                {"id": "A", "value": "20"},
            ],
        },
        {
            "winner_id": "A",
            "relation": "greater",
            "difference": "10",
            "rows": [
                {"id": "A", "value": "20"},
                {"id": "B", "value": "10"},
            ],
        },
        {},
    )
    assert matched is True, details


@pytest.mark.parametrize("observed_period", ["FY2021", "2021-12-31"])
def test_l3_annual_period_equivalence(observed_period: str) -> None:
    matched, details = match_empirical_answer(
        "period_and_value",
        {"result_period": 2021, "value": "10"},
        {"result_period": observed_period, "value": "10"},
        {"target_period": 2021, "target_value": "10"},
    )
    assert matched is True, details


def test_l3_ranked_table_remains_order_sensitive() -> None:
    expected_rows = [
        {"rank": 1, "entity_id": "A", "value": "20"},
        {"rank": 2, "entity_id": "B", "value": "10"},
    ]
    matched, details = match_empirical_answer(
        "ranked_table",
        {"table": expected_rows},
        {"table": list(reversed(expected_rows))},
        {"target_rows": expected_rows, "order_required": True},
    )
    assert matched is False
    assert details["checks"]["table"] is False



def test_l3_contract_retry_includes_failure_feedback() -> None:
    prompt = _contract_repair_prompt(
        "ORIGINAL",
        [{"error_type": "ValueError", "message": "missing answer_payload"}],
    )
    assert prompt.startswith("ORIGINAL")
    assert "missing answer_payload" in prompt
    assert "answer_text" in prompt
    assert "answer_payload" in prompt
