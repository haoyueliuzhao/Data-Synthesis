from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from finraw.db.client import MetadataDB
from finraw.llm_client import JsonCompletion
from finraw.qa.answer_schema_registry import (
    match_answer,
    normalize_model_answer,
    resolve_answer_schema,
)
from finraw.qa.evaluation.contracts import (
    ROLE_DIMENSIONS,
    JudgeContractError,
    normalize_adversarial_payload,
    normalize_judge_payload,
)
from finraw.qa.evaluation.input_views import load_evaluation_bundles
from finraw.qa.evaluation.empirical import (
    _component_scores,
    _contract_repair_prompt,
    _load_evidence_facts,
    _stratified_sample,
    match_empirical_answer,
    match_numeric_answer,
    run_empirical_model_evaluation,
)
from finraw.qa.evaluation.judge import FinancialQualityJudge
from finraw.qa.evaluation.release import build_quality_release
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
        payload = _judge_payload(score, role)
        payload["issue_codes"] = (
            [
                "output_instruction_slightly_formulaic",
                "time_scope_awkward",
            ]
            if role == "surface_financial_analyst"
            else [
                "output_instruction_slightly_formulaic",
                "weak_followup_logic",
            ]
        )
        return payload, {
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
    assert report["subjective_quality"]["mean"] == pytest.approx(86.25)
    assert report["telemetry"]["total_tokens"] == 300
    assert report["issue_codes_by_role"]["surface_financial_analyst"][
        "issue_counts"
    ]["time_scope_awkward"] == 1
    assert report["issue_codes_by_role"]["grounded_qa_auditor"][
        "issue_counts"
    ]["weak_followup_logic"] == 1
    assert report["issue_code_consensus"]["flagged_by_any_judge"][
        "output_instruction_slightly_formulaic"
    ] == 1
    assert report["issue_code_consensus"]["flagged_by_two_or_more"][
        "output_instruction_slightly_formulaic"
    ] == 1
    assert report["issue_code_consensus"]["confirmed_by_adjudicator"] == {}
    feedback = report["generation_feedback"]
    formulaic = feedback["issue_summary"][
        "output_instruction_slightly_formulaic"
    ]
    assert formulaic["target_component"] == "output_contract_verbalizer"
    assert formulaic["flagged_by_any_judge"] == 1
    assert formulaic["flagged_by_two_or_more"] == 1
    assert formulaic["correctness_gate"] is False
    hotspot = next(
        row
        for row in feedback["component_hotspots"]
        if row["issue_code"] == "output_instruction_slightly_formulaic"
    )
    assert hotspot["generation_pipeline"] == "fact_qa"
    assert hotspot["metric_pair"] == "revenue"
    assert hotspot["language"] == "en"
    subtype_slice = report["slices"]["task_subtype"]["single_fact"]
    assert subtype_slice["insufficient_slice_size"] is True
    assert subtype_slice["confidence_intervals_95"]["accepted_rate"]["total"] == 1
    assert subtype_slice["confidence_intervals_95"]["accepted_rate"]["lower"] < 1
    assert all("answer_value" not in json.dumps(view) for view in views)
    assert all("answer_payload" not in json.dumps(view) for view in views)
    assert (output_dir / "qa_quality_evaluation_report.json").exists()
    assert (output_dir / "qa_evaluation_items.jsonl").exists()
    assert (output_dir / "qa_generation_issue_feedback.json").exists()
    assert (output_dir / "qa_generation_issue_hotspots.csv").exists()

    stored = db.fetchone(
        "SELECT decision, subjective_quality_score FROM qa_evaluation_items "
        "WHERE evaluation_run_id = ?",
        (initialized["evaluation_run_id"],),
    )
    assert stored["decision"] == "accepted"
    assert stored["subjective_quality_score"] == pytest.approx(86.25)
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
        judge_function=lambda role, view, rubric: (_judge_payload(4, role), {}),
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
                "rubric_version": "financial_qa_quality.v2",
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


def _judge_payload(
    score: int, role: str | None = None
) -> dict[str, Any]:
    dimensions = ROLE_DIMENSIONS.get(role) if role else (
        "task_authenticity",
        "standalone_financial_value",
        "financial_semantic_validity",
        "clarity_unambiguity",
        "reasoning_necessity",
        "evidence_scope_fit",
        "answer_rubric_fit",
        "language_quality",
    )
    return {
        "rubric_version": "financial_qa_quality.v2",
        "scores": {dimension: score for dimension in dimensions or ()},
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
        "fact_build_id, entity_build_id, metric_build_id, "
        "source_definition_build_id, status, quality_status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "qa_build_eval",
            "kg_eval",
            "v3",
            "fact_build_eval",
            "entity_build_eval",
            "metric_build_eval",
            "source_definition_build_eval",
            "complete",
            "passed",
        ),
    )
    db.execute(
        "INSERT INTO canonical_entities (entity_id, canonical_name, entity_type, "
        "build_id) VALUES (?, ?, ?, ?)",
        ("AAPL_US", "Apple", "company", "entity_build_eval"),
    )
    db.execute(
        "INSERT INTO metrics (metric_id, canonical_name, build_id) "
        "VALUES (?, ?, ?)",
        ("revenue", "Revenue", "metric_build_eval"),
    )
    db.execute(
        "INSERT INTO source_metric_definitions (definition_id, source_id, "
        "metric_id, definition_text, build_id) VALUES (?, ?, ?, ?, ?)",
        (
            "definition_revenue_eval",
            "sec_companyfacts",
            "revenue",
            "SEC revenue definition",
            "source_definition_build_eval",
        ),
    )
    db.execute(
        "INSERT INTO standardized_facts (fact_id, build_id, entity_id, metric_id, "
        "normalized_value, normalized_unit, normalized_currency, fiscal_year, "
        "source_id, source_definition_id, raw_object_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "fact_secret",
            "fact_build_eval",
            "AAPL_US",
            "revenue",
            "383285",
            "million USD",
            "USD",
            2023,
            "sec_companyfacts",
            "definition_revenue_eval",
            "raw_secret",
        ),
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
    from finraw.qa.evaluation.required_checks import required_checks_for

    for check_name in required_checks_for("fact_qa", {}):
        db.execute(
            "INSERT INTO qa_quality_checks (check_id, qa_id, qa_build_id, "
            "check_name, check_status) VALUES (?, ?, ?, ?, ?)",
            (
                "check_eval_" + check_name,
                "qa_eval",
                "qa_build_eval",
                check_name,
                (
                    "failed"
                    if failed_l0 and check_name == "independent_recompute"
                    else "passed"
                ),
            ),
        )
    return db



def test_llm_secondary_review_replaces_pending_manual_step(tmp_path: Path) -> None:
    db = _db_with_sample(tmp_path, failed_l0=False)
    config = _config()
    quality = config["qa"]["quality_evaluation"]
    quality["calibration"]["required"] = False
    quality["calibration"]["replacement_mode"] = "llm_secondary_review"
    initialized = init_quality_evaluation(db, config, "qa_build_eval")

    def base_with_one_dispute(
        role: str, view: dict[str, Any], rubric: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        payload = _judge_payload(5, role)
        if role == "surface_financial_analyst":
            payload["scores"]["language_quality"] = 3
        return payload, {}

    first = run_quality_evaluation(
        db,
        initialized["evaluation_run_id"],
        judge_function=base_with_one_dispute,
    )
    assert first["decision_counts"] == {"manual_review": 1}
    assert first["risk_router"]["status_counts"] == {
        "adversarial_challenge_pending": 1
    }
    assert first["judge_disagreement"]["unresolved_sources"][
        "reason_counts"
    ]["adjudicator_pending"] == 1
    assert first["adjudication"]["required_count"] == 1
    assert first["adjudication"]["pending_count"] == 1

    def adversarial(
        role: str, view: dict[str, Any], rubric: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        assert role == "adversarial_reviewer"
        dimensions = view["reviewed_dimensions"]
        return {
            "rubric_version": "financial_qa_quality.v2",
            "reviewed_dimensions": dimensions,
            "resolutions": {
                dimension: {
                    "decision": "uphold",
                    "resolved_score": view["provisional_evaluation"][
                        "dimension_scores"
                    ][dimension],
                    "reason": "The provisional score is supported.",
                }
                for dimension in dimensions
            },
            "confirmed_fatal_flags": [],
            "issue_codes": ["output_instruction_slightly_formulaic"],
            "confidence": 0.9,
            "escalate_to_human": False,
            "brief_justification": {
                "financial_value": "The task remains useful.",
                "main_weakness": "The language is somewhat mechanical.",
            },
        }, {}

    final = adjudicate_quality_run(
        db,
        initialized["evaluation_run_id"],
        judge_function=adversarial,
    )
    assert final["decision_counts"] == {"accepted": 1}
    assert final["population"]["judge_call_success_count"] == 3
    assert final["issue_code_consensus"]["confirmed_by_adjudicator"][
        "output_instruction_slightly_formulaic"
    ] == 1
    assert final["adjudication"]["completed_count"] == 1
    assert final["adjudication"]["pending_count"] == 0
    assert final["adjudication"]["resolution_decision_counts"] == {
        "uphold": 1
    }
    assert final["adjudication"]["score_delta"]["mean"] == 0
    stored = db.fetchone(
        "SELECT judge_disagreement FROM qa_evaluation_items "
        "WHERE evaluation_run_id = ?",
        (initialized["evaluation_run_id"],),
    )
    trace = json.loads(stored["judge_disagreement"])[
        "adjudication_trace"
    ]
    assert trace["base_threshold_decision"] == "accepted"
    assert trace["final_decision"] == "accepted"
    assert trace["score_delta"] == 0
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
            assert '"answer_value"' not in prompt
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
                "ranking_table": [
                    {"rank": 1, "entity_id": "A", "value": "7.32"}
                ],
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
            "screening_table": [
                {
                    "entity_id": "A",
                    "revenue_growth_pct": "10",
                    "net_margin_pct": "5",
                    "debt_ratio_pct": "30",
                }
            ],
            "filter_metadata": {},
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
    assert details["checks"]["screening_table"] is False



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
        {"ranking_table": list(reversed(expected_rows))},
        {"target_rows": expected_rows, "order_required": True},
    )
    assert matched is False
    assert details["checks"]["ranking_table"] is False



def test_l3_contract_retry_includes_failure_feedback() -> None:
    prompt = _contract_repair_prompt(
        "ORIGINAL",
        [{"error_type": "ValueError", "message": "missing answer_payload"}],
    )
    assert prompt.startswith("ORIGINAL")
    assert "missing answer_payload" in prompt
    assert "answer_text" in prompt
    assert "answer_payload" in prompt



def test_l0_missing_required_check_fails_closed(tmp_path: Path) -> None:
    db = _db_with_sample(tmp_path, failed_l0=False)
    db.execute(
        "DELETE FROM qa_quality_checks WHERE qa_id = ? AND check_name = ?",
        ("qa_eval", "question_semantic_reparse"),
    )
    bundle = load_evaluation_bundles(db, "qa_build_eval")[0]
    assert bundle["deterministic_gate_status"] == "failed"
    assert any(
        reason.startswith("missing_quality_checks=")
        and "question_semantic_reparse" in reason
        for reason in bundle["deterministic_gate_reasons"]
    )
    assert bundle["required_check_manifest_hash"]
    db.close()


def test_l2_contract_retry_includes_previous_failure() -> None:
    prompts: list[str] = []

    class RepairClient:
        def complete_json(self, prompt: str, *, temperature: float) -> JsonCompletion:
            prompts.append(prompt)
            payload = (
                {"scores": {}}
                if len(prompts) == 1
                else _judge_payload(4, "surface_financial_analyst")
            )
            return JsonCompletion(payload, {"response_model": "fixture"})

    judge = FinancialQualityJudge({"max_contract_attempts": 2, "llm": {}})
    judge._clients["surface_financial_analyst"] = RepairClient()
    payload, telemetry = judge.evaluate(
        "surface_financial_analyst",
        {"question": "What was revenue?"},
        {"benchmark_task": "T2"},
    )
    assert payload["scores"]["task_authenticity"] == 4
    assert telemetry["contract_attempt"] == 2
    assert len(prompts) == 2
    assert "CONTRACT REPAIR REQUIRED" in prompts[1]
    assert "Score dimensions mismatch" in prompts[1]


def test_adversarial_contract_reviews_only_disputed_dimensions() -> None:
    payload = {
        "reviewed_dimensions": ["reasoning_necessity"],
        "resolutions": {
            "reasoning_necessity": {
                "decision": "downgrade",
                "resolved_score": 2,
                "reason": "The second operation is not necessary.",
            }
        },
        "confirmed_fatal_flags": [],
        "issue_codes": ["gratuitous_complexity"],
        "confidence": 0.9,
        "escalate_to_human": False,
        "brief_justification": {
            "financial_value": "Some value remains.",
            "main_weakness": "The reasoning chain is inflated.",
        },
    }
    normalized = normalize_adversarial_payload(
        payload, ["reasoning_necessity"]
    )
    assert normalized["scores"] == {}
    assert normalized["issue_codes"] == ["gratuitous_complexity"]
    assert normalized["resolutions"]["reasoning_necessity"][
        "resolved_score"
    ] == 2
    with pytest.raises(JudgeContractError, match="Reviewed dimensions mismatch"):
        normalize_adversarial_payload(
            payload, ["reasoning_necessity", "financial_semantic_validity"]
        )


def test_l3_evidence_is_pinned_to_qa_build_versions(tmp_path: Path) -> None:
    db = _db_with_sample(tmp_path, failed_l0=False)
    facts = _load_evidence_facts(db, "qa_build_eval", ["fact_secret"])
    assert len(facts) == 1
    assert facts[0]["fact_build_id"] == "fact_build_eval"
    assert facts[0]["entity_build_id"] == "entity_build_eval"
    assert facts[0]["metric_build_id"] == "metric_build_eval"
    assert (
        facts[0]["source_definition_build_id"]
        == "source_definition_build_eval"
    )
    db.close()


def test_filtered_rank_followup_uses_sectioned_schema_contract() -> None:
    rubric = {
        "requested_unit": "percent",
        "unit_must_match": True,
        "order_required": True,
        "value_tolerance": "0.001",
        "growth_threshold_pct": "10",
    }
    schema = resolve_answer_schema(
        "filtered_rank_followup",
        {
            "type": "filtered_rank_followup",
            "top_k": 3,
            "followup_rank": 1,
        },
        rubric,
        {"thresholds": {"revenue_growth_pct": {"comparison": "gt", "value": "10"}}},
    )
    expected = {
        "ranking_table": [
            {"rank": 1, "entity_id": "A", "value": "20"},
            {"rank": 2, "entity_id": "B", "value": "15"},
        ],
        "table": [
            {
                "rank": 1,
                "entity_id": "A",
                "primary_value": "20",
                "secondary_value": "35",
            }
        ],
        "primary_unit": "percent",
        "secondary_unit": "percent",
    }
    observed = {
        "ranking_table": [
            {"rank": 1, "entity_id": "A", "value": "20"},
            {"rank": 2, "entity_id": "B", "value": "15"},
        ],
        "followup_table": [
            {"rank": 1, "entity_id": "A", "value": "35"}
        ],
        "metadata": {
            "top_k": 3,
            "followup_rank": 1,
            "thresholds": schema["thresholds"],
            "scope": {},
        },
        "primary_unit": "percent",
        "secondary_unit": "percent",
    }
    matched, details = match_answer(schema, expected, observed, rubric)
    assert matched is True, details
    with pytest.raises(ValueError, match="ranking_table"):
        normalize_model_answer(
            {
                "answer_text": "A ranks first.",
                "answer_payload": {"table": expected["table"]},
            },
            schema,
        )

def test_quality_release_selects_only_accepted_training_items(
    tmp_path: Path,
) -> None:
    db = _db_with_sample(tmp_path, failed_l0=False)
    config = _config()
    initialized = init_quality_evaluation(db, config, "qa_build_eval")
    run_quality_evaluation(
        db,
        initialized["evaluation_run_id"],
        judge_function=lambda role, view, rubric: (
            _judge_payload(5, role),
            {},
        ),
    )

    output_dir = tmp_path / "release"
    report = build_quality_release(
        db,
        initialized["evaluation_run_id"],
        output_dir=str(output_dir),
    )

    assert report["status"] == "draft_advisory"
    assert report["eligible_count"] == 1
    assert report["selected_count"] == 1
    assert report["selected_split_counts"] == {"train": 1}
    member = db.fetchone(
        "SELECT is_selected, selection_reason "
        "FROM qa_quality_release_members WHERE quality_release_id = ?",
        (report["quality_release_id"],),
    )
    assert bool(member["is_selected"]) is True
    assert json.loads(member["selection_reason"])["eligible"] is True
    assert (output_dir / "qa_quality_release_report.json").exists()
    db.close()


def test_quality_release_never_selects_evaluation_holdouts(
    tmp_path: Path,
) -> None:
    db = _db_with_sample(tmp_path, failed_l0=False)
    db.execute("UPDATE qa_samples SET split = 'dev' WHERE qa_id = 'qa_eval'")
    initialized = init_quality_evaluation(db, _config(), "qa_build_eval")
    run_quality_evaluation(
        db,
        initialized["evaluation_run_id"],
        judge_function=lambda role, view, rubric: (
            _judge_payload(5, role),
            {},
        ),
    )

    report = build_quality_release(db, initialized["evaluation_run_id"])

    assert report["decision_counts"] == {"accepted": 1}
    assert report["eligible_count"] == 0
    assert report["selected_count"] == 0
    assert report["exclusion_reason_counts"]["evaluation_holdout_split:dev"] == 1
    db.close()


def test_release_gate_requires_frozen_calibration_thresholds(
    tmp_path: Path,
) -> None:
    db = _db_with_sample(tmp_path, failed_l0=False)
    initialized = init_quality_evaluation(
        db,
        _config(),
        "qa_build_eval",
        evaluation_mode="release_gate",
    )
    run_quality_evaluation(
        db,
        initialized["evaluation_run_id"],
        judge_function=lambda role, view, rubric: (
            _judge_payload(5, role),
            {},
        ),
    )

    with pytest.raises(RuntimeError, match="human-calibrated thresholds"):
        build_quality_release(db, initialized["evaluation_run_id"])
    db.close()


def test_unresolved_adversarial_challenge_is_quarantined(
    tmp_path: Path,
) -> None:
    db = _db_with_sample(tmp_path, failed_l0=False)
    config = _config()
    quality = config["qa"]["quality_evaluation"]
    quality["calibration"]["replacement_mode"] = "llm_secondary_review"
    initialized = init_quality_evaluation(db, config, "qa_build_eval")

    def disputed_base(
        role: str, view: dict[str, Any], rubric: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        payload = _judge_payload(5, role)
        if role == "surface_financial_analyst":
            payload["scores"]["language_quality"] = 3
        return payload, {}

    run_quality_evaluation(
        db,
        initialized["evaluation_run_id"],
        judge_function=disputed_base,
    )

    def escalating_adversarial(
        role: str, view: dict[str, Any], rubric: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        dimensions = view["reviewed_dimensions"]
        return {
            "rubric_version": "financial_qa_quality.v2",
            "reviewed_dimensions": dimensions,
            "resolutions": {
                dimension: {
                    "decision": "escalate",
                    "resolved_score": None,
                    "reason": "The dispute cannot be resolved reliably.",
                }
                for dimension in dimensions
            },
            "confirmed_fatal_flags": [],
            "issue_codes": [],
            "confidence": 0.7,
            "escalate_to_human": True,
            "brief_justification": {
                "financial_value": "Uncertain.",
                "main_weakness": "The semantic dispute remains unresolved.",
            },
        }, {}

    output_dir = tmp_path / "quarantine"
    report = adjudicate_quality_run(
        db,
        initialized["evaluation_run_id"],
        output_dir=str(output_dir),
        judge_function=escalating_adversarial,
    )

    assert report["decision_counts"] == {
        "quarantined_judge_disagreement": 1
    }
    assert report["risk_router"]["status_counts"] == {
        "quarantined_judge_disagreement": 1
    }
    quarantine = output_dir / "judge_disagreement_quarantine.jsonl"
    assert quarantine.exists()
    assert len(quarantine.read_text(encoding="utf-8").splitlines()) == 1
    release = build_quality_release(db, initialized["evaluation_run_id"])
    assert release["selected_count"] == 0
    db.close()

def _l3_mode_config(mode: str) -> dict[str, Any]:
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
        "mode": mode,
        "maximum_concurrency": 1,
        "max_contract_attempts": 2,
        "distractor_count": 3,
        "maximum_tool_rounds": 6,
        "supported_answer_types": ["numeric"],
        "models": [
            {"model_role": "pro", "model": "deepseek-v4-pro"},
            {"model_role": "flash", "model": "deepseek-v4-flash"},
        ],
    }
    return config


@pytest.mark.parametrize(
    "mode",
    ["gold_plan_given", "evidence_only", "evidence_pool"],
)
def test_l3_modes_a_to_c_have_distinct_inputs_and_fixed_metrics(
    tmp_path: Path,
    mode: str,
) -> None:
    db = _db_with_sample(tmp_path, failed_l0=False)

    class ModeClient:
        def __init__(self, model_config: dict[str, Any]):
            self.model = model_config["model"]

        def complete_json(
            self,
            prompt: str,
            *,
            temperature: float,
        ) -> JsonCompletion:
            assert f'"evaluation_mode": "{mode}"' in prompt
            assert '"evidence_facts"' in prompt
            if mode == "gold_plan_given":
                assert '"operation_plan"' in prompt
            else:
                assert '"operation_plan"' not in prompt
            payload = {
                "answer_text": "383285 million USD",
                "answer_payload": {
                    "value": "383285",
                    "unit": "million USD",
                    "currency": "USD",
                },
            }
            if mode == "evidence_pool":
                payload["selected_evidence_ids"] = ["fact_secret"]
            return JsonCompletion(
                payload,
                {
                    "provider": "fixture",
                    "model_selected": self.model,
                    "response_model": self.model,
                    "total_tokens": 10,
                },
            )

    report = run_empirical_model_evaluation(
        db,
        _l3_mode_config(mode),
        ["qa_build_eval"],
        limit=1,
        client_factory=ModeClient,
    )

    assert report["evaluation_mode"] == mode
    assert report["overall"]["api_call_success_rate"] == 1.0
    assert report["overall"]["contract_success_rate"] == 1.0
    assert (
        report["overall"]["semantic_accuracy_given_valid_contract"]
        == 1.0
    )
    assert report["overall"]["end_to_end_accuracy"] == 1.0
    if mode == "evidence_pool":
        assert (
            report["overall"]["evidence_selection_correct_rate"]
            == 1.0
        )
    else:
        assert (
            report["overall"]["evidence_selection_correct_rate"]
            is None
        )
    db.close()


def test_l3_mode_d_executes_registered_tools_before_answering(
    tmp_path: Path,
) -> None:
    db = _db_with_sample(tmp_path, failed_l0=False)
    db.execute(
        "UPDATE standardized_facts SET graph_ready = 1 "
        "WHERE fact_id = 'fact_secret'"
    )

    class ToolClient:
        def __init__(self, model_config: dict[str, Any]):
            self.model = model_config["model"]
            self.round = 0

        def complete_json(
            self,
            prompt: str,
            *,
            temperature: float,
        ) -> JsonCompletion:
            self.round += 1
            assert '"evaluation_mode": "retrieval_tool"' in prompt
            assert '"evidence_facts"' not in prompt
            if self.round == 1:
                payload = {
                    "action": "tool_call",
                    "tool": "search_entities",
                    "arguments": {"query": "Apple"},
                }
            elif self.round == 2:
                assert "AAPL_US" in prompt
                payload = {
                    "action": "tool_call",
                    "tool": "search_metrics",
                    "arguments": {"query": "Revenue"},
                }
            elif self.round == 3:
                assert '"metric_id": "revenue"' in prompt
                payload = {
                    "action": "tool_call",
                    "tool": "search_facts",
                    "arguments": {
                        "entity_id": "AAPL_US",
                        "metric_id": "revenue",
                        "fiscal_year": 2023,
                    },
                }
            else:
                assert "fact_secret" in prompt
                payload = {
                    "action": "final",
                    "answer_text": "383285 million USD",
                    "answer_payload": {
                        "value": "383285",
                        "unit": "million USD",
                        "currency": "USD",
                    },
                    "selected_evidence_ids": ["fact_secret"],
                }
            return JsonCompletion(
                payload,
                {
                    "provider": "fixture",
                    "model_selected": self.model,
                    "response_model": self.model,
                    "total_tokens": 10,
                },
            )

    report = run_empirical_model_evaluation(
        db,
        _l3_mode_config("retrieval_tool"),
        ["qa_build_eval"],
        limit=1,
        client_factory=ToolClient,
    )

    assert report["evaluation_mode"] == "retrieval_tool"
    assert report["overall"]["contract_success_rate"] == 1.0
    assert report["overall"]["evidence_selection_correct_rate"] == 1.0
    assert report["overall"]["end_to_end_accuracy"] == 1.0
    trials = db.fetchall(
        "SELECT tool_trace, selected_evidence_ids, end_to_end_correct "
        "FROM qa_empirical_model_trials"
    )
    assert len(trials) == 2
    assert all(len(json.loads(row["tool_trace"])) == 3 for row in trials)
    assert all(
        json.loads(row["selected_evidence_ids"]) == ["fact_secret"]
        for row in trials
    )
    assert all(bool(row["end_to_end_correct"]) for row in trials)
    db.close()


def test_l3_separates_api_success_from_json_contract_success(
    tmp_path: Path,
) -> None:
    db = _db_with_sample(tmp_path, failed_l0=False)

    class InvalidContractClient:
        def __init__(self, model_config: dict[str, Any]):
            self.model = model_config["model"]

        def complete_json(
            self,
            prompt: str,
            *,
            temperature: float,
        ) -> JsonCompletion:
            return JsonCompletion(
                {"answer": "383285"},
                {
                    "provider": "fixture",
                    "model_selected": self.model,
                    "response_model": self.model,
                    "total_tokens": 5,
                },
            )

    report = run_empirical_model_evaluation(
        db,
        _l3_mode_config("evidence_only"),
        ["qa_build_eval"],
        limit=1,
        client_factory=InvalidContractClient,
    )

    assert report["overall"]["api_call_success_rate"] == 1.0
    assert report["overall"]["contract_success_rate"] == 0.0
    assert (
        report["overall"]["semantic_accuracy_given_valid_contract"]
        == 0.0
    )
    assert report["overall"]["end_to_end_accuracy"] == 0.0
    assert report["status"] == "partial"
    db.close()

def test_l3_semantic_correctness_is_separate_from_unit_currency(
    tmp_path: Path,
) -> None:
    db = _db_with_sample(tmp_path, failed_l0=False)
    db.execute(
        "UPDATE qa_samples SET rubric = ? WHERE qa_id = ?",
        (
            json.dumps(
                {
                    "match_type": "numeric",
                    "requested_unit": "million USD",
                    "requested_currency": "USD",
                    "unit_must_match": True,
                }
            ),
            "qa_eval",
        ),
    )

    class WrongUnitClient:
        def __init__(self, model_config: dict[str, Any]):
            self.model = model_config["model"]

        def complete_json(
            self,
            prompt: str,
            *,
            temperature: float,
        ) -> JsonCompletion:
            return JsonCompletion(
                {
                    "answer_text": "383285 million EUR",
                    "answer_payload": {
                        "value": "383285",
                        "unit": "million EUR",
                        "currency": "EUR",
                    },
                },
                {
                    "provider": "fixture",
                    "model_selected": self.model,
                    "response_model": self.model,
                },
            )

    report = run_empirical_model_evaluation(
        db,
        _l3_mode_config("evidence_only"),
        ["qa_build_eval"],
        limit=1,
        client_factory=WrongUnitClient,
    )

    assert (
        report["overall"]["semantic_accuracy_given_valid_contract"]
        == 1.0
    )
    assert report["overall"]["unit_currency_correct_rate"] == 0.0
    assert report["overall"]["end_to_end_accuracy"] == 0.0
    db.close()


def test_l3_table_completeness_and_order_are_independent_components() -> None:
    rubric = {
        "order_required": True,
        "target_rows": [
            {"rank": 1, "entity_id": "A", "value": "20"},
            {"rank": 2, "entity_id": "B", "value": "10"},
        ],
    }
    schema = resolve_answer_schema(
        "ranked_table",
        {"type": "ranked_table"},
        rubric,
    )
    expected = {"ranking_table": rubric["target_rows"]}
    reversed_rows = {
        "ranking_table": list(reversed(rubric["target_rows"])),
    }
    matched, details = match_answer(
        schema,
        expected,
        reversed_rows,
        rubric,
    )
    assert matched is False
    scores = _component_scores(
        schema,
        expected,
        reversed_rows,
        rubric,
        details,
        "evidence_only",
        set(),
        set(),
        api_call_success=True,
        json_contract_success=True,
    )
    assert scores["row_completeness"] is True
    assert scores["order_correct"] is False
    assert scores["end_to_end_correct"] is False

    incomplete = {"ranking_table": rubric["target_rows"][:1]}
    matched, details = match_answer(schema, expected, incomplete, rubric)
    assert matched is False
    scores = _component_scores(
        schema,
        expected,
        incomplete,
        rubric,
        details,
        "evidence_only",
        set(),
        set(),
        api_call_success=True,
        json_contract_success=True,
    )
    assert scores["row_completeness"] is False
    assert scores["order_correct"] is False
