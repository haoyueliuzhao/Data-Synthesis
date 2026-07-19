from __future__ import annotations

from dataclasses import replace

from finraw.analysis.claims import build_claim_plan
from finraw.analysis.generator import (
    ANALYSIS_RESPONSE_SCHEMA_VERSION,
    generate_analysis,
    validate_analysis_response,
)
from finraw.analysis.registry import analysis_pattern_registry, signal_registry
from finraw.analysis.semantic_constraints import validate_signal_semantics
from finraw.analysis.semantic_frames import default_surface_form_id
from finraw.analysis.text_semantics import validate_numeric_grounding, validate_stance


def _fact(
    fact_id: str,
    metric_id: str,
    year: int,
    value: float,
    *,
    source_id: str = "sec_companyfacts",
) -> dict:
    return {
        "fact_id": fact_id,
        "entity_id": "A_US",
        "entity_scope_id": "A_US",
        "financial_scope_type": "consolidated_entity",
        "metric_id": metric_id,
        "normalized_value": value,
        "normalized_unit": "million USD",
        "normalized_currency": "USD",
        "period_start": f"{year}-01-01",
        "period_end": f"{year}-12-31",
        "fiscal_year": year,
        "fiscal_quarter": "FY",
        "time_basis": "fiscal_year",
        "metric_period_type": "period_flow",
        "source_definition_id": f"def_{metric_id}",
        "frequency": "annual",
        "seasonal_adjustment": "not_applicable",
        "vintage_policy": "latest_filing",
        "is_forecast": 0,
        "source_id": source_id,
        "graph_ready": 1,
    }


def _signal(signal_id: str, spec_id: str, direction: str, value: str) -> dict:
    return {
        "signal_id": signal_id,
        "signal_spec_id": spec_id,
        "direction": direction,
        "strength": "moderate",
        "confidence": 0.98,
        "signal_payload": {
            "first_value": "100",
            "last_value": "112.4",
            "growth_pct": value,
        },
    }


def _operating_claim_plan():
    pattern = analysis_pattern_registry()["operating_trend_summary_v1"]
    signals = [
        _signal("signal_revenue", "revenue_growth_v1", "positive", "12.4"),
        _signal("signal_profit", "profit_growth_v1", "positive", "8.0"),
        _signal(
            "signal_cash",
            "operating_cash_flow_growth_v1",
            "negative",
            "-3.1",
        ),
    ]
    return (
        pattern,
        signals,
        build_claim_plan(
            pattern,
            signals,
            entity_name="Company A",
            scope_definition="Company A consolidated",
        ),
    )


class _Provider:
    def __init__(self, payload: dict):
        self.payload = payload
        self.last_telemetry = {
            "provider": "fake",
            "http_success": True,
            "json_valid": True,
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        }

    def generate(self, request: dict) -> dict:
        return self.payload


class _SequenceProvider:
    def __init__(self, payloads: list[dict]):
        self.payloads = iter(payloads)
        self.attempt = 0
        self.last_telemetry = {}

    def generate(self, request: dict) -> dict:
        self.attempt += 1
        self.last_telemetry = {
            "provider": "fake",
            "http_success": True,
            "json_valid": True,
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "request_hash": f"request_{self.attempt}",
        }
        return next(self.payloads)


def _semantic_frame_payload(plan):
    mandatory = [claim for claim in plan.claims if claim["is_required"]]
    conclusion = next(
        item
        for item in plan.valid_conclusions
        if item["conclusion_id"] == plan.selected_conclusion_id
    )
    return {
        "schema_version": ANALYSIS_RESPONSE_SCHEMA_VERSION,
        "selected_conclusion_id": plan.selected_conclusion_id,
        "claims": [
            {
                "claim_id": claim["claim_id"],
                "semantic_frame": claim["semantic_frame"],
                "surface_form_id": default_surface_form_id(
                    claim["semantic_frame"], kind="claim"
                ),
                "evidence_ids": claim["support_signal_ids"],
            }
            for claim in mandatory
        ],
        "conclusion_semantic_frame": conclusion["semantic_frame"],
        "conclusion_surface_form_id": default_surface_form_id(
            conclusion["semantic_frame"], kind="conclusion"
        ),
        "caveats": [{"caveat_id": caveat["caveat_id"]} for caveat in plan.caveats],
    }


def test_controlled_analysis_generation_keeps_auditable_frame_contract():
    pattern, _, plan = _operating_claim_plan()
    result = generate_analysis(
        pattern,
        plan,
        [],
        config={"mode": "controlled_llm"},
        provider=_Provider(_semantic_frame_payload(plan)),
    )
    assert result.generation_method == "controlled_llm_semantic_frame"
    assert result.generation_metadata["schema_valid"] is True
    assert result.generation_metadata["llm_telemetry"]["total_tokens"] == 150
    assert result.numeric_slots
    assert all(item["semantic_frame"] for item in result.claim_alignment)
    assert all(item["surface_form_id"] for item in result.claim_alignment)


def test_free_text_semantic_reversal_is_rejected_then_frame_payload_is_accepted():
    pattern, _, plan = _operating_claim_plan()
    valid_payload = _semantic_frame_payload(plan)
    invalid_payload = {
        **valid_payload,
        "claims": [dict(item) for item in valid_payload["claims"]],
    }
    mandatory = [claim for claim in plan.claims if claim["is_required"]]
    risk_index = next(
        index for index, claim in enumerate(mandatory) if claim["claim_role"] == "risk"
    )
    invalid_payload["claims"][risk_index]["surface_text"] = (
        "Operating cash flow strongly supports profit growth and is not a material "
        "risk caveat."
    )
    validation = validate_analysis_response(invalid_payload, plan)
    assert not validation["passed"]
    assert "claim_fields_mismatch" in validation["errors"]

    provider = _SequenceProvider([invalid_payload, valid_payload])
    result = generate_analysis(
        pattern,
        plan,
        [],
        config={"mode": "controlled_llm", "max_attempts": 2},
        provider=provider,
    )

    assert result.generation_method == "controlled_llm_semantic_frame"
    attempts = result.generation_metadata["llm_attempts"]
    assert len(attempts) == 2
    assert attempts[0]["structured_response_valid"] is False
    assert "claim_fields_mismatch" in attempts[0]["validation_errors"]
    assert attempts[1]["structured_response_valid"] is True
    assert "strongly supports profit growth" not in result.analysis_text


def test_legacy_keyword_stance_parser_is_not_a_claim_acceptance_gate():
    adversarial = (
        "Operating cash flow strongly supports profit growth and is not a material "
        "risk caveat."
    )
    assert validate_stance(adversarial, "risk")["passed"]
    _, _, plan = _operating_claim_plan()
    payload = _semantic_frame_payload(plan)
    risk_index = next(
        index
        for index, claim in enumerate(
            [claim for claim in plan.claims if claim["is_required"]]
        )
        if claim["claim_role"] == "risk"
    )
    payload["claims"][risk_index]["surface_text"] = adversarial
    assert not validate_analysis_response(payload, plan)["passed"]


def test_numeric_grounding_accepts_registered_slot_and_rejects_wrong_value_or_unit():
    slots = [
        {
            "slot_id": "signal_revenue.growth_pct",
            "value": "12.4",
            "unit": "percent",
            "tolerance": "0.01",
        }
    ]
    assert validate_numeric_grounding(
        "Revenue increased 12.4% in 2023.",
        slots,
        [2023],
    )["passed"]
    wrong_value = validate_numeric_grounding(
        "Revenue increased 14.4% in 2023.",
        slots,
        [2023],
    )
    assert not wrong_value["passed"]
    wrong_unit = validate_numeric_grounding(
        "Revenue increased by 12.4 percentage points in 2023.",
        slots,
        [2023],
    )
    assert not wrong_unit["passed"]
    assert wrong_unit["unit_mismatches"]


def test_signal_semantic_gate_rejects_source_drift_and_unknown_operator():
    spec = signal_registry()["revenue_growth_v1"]
    facts = [
        _fact("revenue_2021", "revenue", 2021, 100),
        _fact("revenue_2022", "revenue", 2022, 110),
        _fact(
            "revenue_2023",
            "revenue",
            2023,
            120,
            source_id="other_source",
        ),
    ]
    drift = validate_signal_semantics(spec, {"series": facts})
    assert not drift["passed"]
    assert "analysis_signal_source_id" in drift["errors"]

    unknown = replace(
        spec,
        semantic_constraints=(
            *spec.semantic_constraints,
            {"field": "periods", "operator": "unregistered_operator"},
        ),
    )
    rejected = validate_signal_semantics(
        unknown,
        {
            "series": [
                _fact(f"revenue_{year}", "revenue", year, value)
                for year, value in ((2021, 100), (2022, 110), (2023, 120))
            ]
        },
    )
    assert not rejected["passed"]
    assert any("analysis_constraint_unknown" in error for error in rejected["errors"])


def test_claim_plan_has_relations_and_only_predicate_valid_conclusions():
    pattern, _, plan = _operating_claim_plan()
    synthesis = [claim for claim in plan.claims if claim["claim_role"] == "synthesis"]
    risks = [claim for claim in plan.claims if claim["claim_role"] == "risk"]
    assert len(synthesis) == 1
    assert synthesis[0]["depends_on_claim_ids"]
    assert risks
    assert all(
        claim["contradicts_claim_ids"] == [synthesis[0]["claim_id"]] for claim in risks
    )
    valid_ids = {item["conclusion_id"] for item in plan.valid_conclusions}
    assert plan.selected_conclusion_id in valid_ids
    assert "broadly_positive" not in valid_ids
    assert all(item["conditions"] for item in plan.valid_conclusions)


def test_component_split_keeps_shared_entities_and_peer_scope_together():
    from finraw.analysis.split import split_analysis_samples

    rows = [
        {
            "analysis_sample_id": "sample_a_1",
            "analysis_semantic_cluster_id": "cluster_a_1",
            "signal_composition_id": "composition_growth",
            "analysis_pattern_id": "operating_trend_summary_v1",
            "entity_ids": ["A_US"],
            "period_scope": {"years": [2019, 2020, 2021]},
            "difficulty_features": {"counter_claim_count": 0},
            "scope_definition": "A consolidated",
        },
        {
            "analysis_sample_id": "sample_a_2",
            "analysis_semantic_cluster_id": "cluster_a_2",
            "signal_composition_id": "composition_quality",
            "analysis_pattern_id": "growth_quality_diagnosis_v1",
            "entity_ids": ["A_US"],
            "period_scope": {"years": [2020, 2021, 2022]},
            "difficulty_features": {"counter_claim_count": 2},
            "scope_definition": "A consolidated",
        },
        {
            "analysis_sample_id": "sample_peer",
            "analysis_semantic_cluster_id": "cluster_peer",
            "signal_composition_id": "composition_peer",
            "analysis_pattern_id": "peer_positioning_v1",
            "entity_ids": ["A_US", "B_US"],
            "period_scope": {"years": [2022, 2023]},
            "difficulty_features": {"counter_claim_count": 1},
            "scope_definition": "Technology complete peer set",
        },
    ]

    class FakeDB:
        def __init__(self):
            self.updates = {}

        def fetchall(self, sql, params):
            return rows

        def execute(self, sql, params):
            split, sample_id = params
            self.updates[sample_id] = split

    db = FakeDB()
    report = split_analysis_samples(db, "analysis_build_test", {})
    assert len(set(db.updates.values())) == 1
    assert report["component_count"] == 1
    assert report["leakage_audit"]["passed"] is True
    assert report["leakage_audit"]["entity_cross_split_count"] == 0
    assert report["leakage_audit"]["peer_scope_cross_split_count"] == 0


def test_qa_api_telemetry_counts_fallback_independently_from_qa_validity():
    from finraw.qa.pipeline import _qa_llm_generation_stats

    class FakeDB:
        def fetchall(self, sql, params):
            return [
                {
                    "generation_method": "controlled_llm_sentence_plan",
                    "source_metadata": {
                        "question_generation": {
                            "fallback_reason": None,
                            "llm_telemetry": {
                                "http_success": True,
                                "json_valid": True,
                                "sentence_plan_valid": True,
                                "latency_ms": 100,
                                "total_tokens": 25,
                            },
                        }
                    },
                },
                {
                    "generation_method": "deterministic_template_fallback",
                    "source_metadata": {
                        "question_generation": {
                            "fallback_reason": "llm_unavailable:TimeoutError",
                            "llm_telemetry": {
                                "http_success": False,
                                "json_valid": False,
                                "sentence_plan_valid": False,
                                "latency_ms": 90000,
                            },
                        }
                    },
                },
            ]

    stats = _qa_llm_generation_stats(
        FakeDB(),
        "qa_build_test",
        {"question_generation": {"mode": "controlled_llm"}},
    )
    assert stats["request_count"] == 2
    assert stats["http_success_rate"] == 0.5
    assert stats["controlled_generation_rate"] == 0.5
    assert stats["fallback_rate"] == 0.5
    assert stats["fallback_reason_distribution"] == {"llm_unavailable:TimeoutError": 1}


def test_shared_llm_client_records_telemetry_without_prompt_response_or_key(
    monkeypatch,
):
    import json
    import urllib.request

    from finraw.llm_client import OpenAICompatibleJsonClient

    secret = "test-secret-not-for-storage"
    monkeypatch.setenv("FINRAW_TEST_API_KEY", secret)

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return json.dumps(
                {
                    "id": "response_test",
                    "model": "model-test",
                    "choices": [
                        {"message": {"content": json.dumps({"result": "valid"})}}
                    ],
                    "usage": {
                        "prompt_tokens": 20,
                        "completion_tokens": 5,
                        "total_tokens": 25,
                    },
                }
            ).encode()

    monkeypatch.setattr(urllib.request, "urlopen", lambda request, timeout: Response())
    client = OpenAICompatibleJsonClient(
        {
            "endpoint": "https://example.test/v1/chat/completions",
            "model": "model-test",
            "api_key_env": "FINRAW_TEST_API_KEY",
        }
    )
    completion = client.complete_json("private compact evidence")
    serialized = json.dumps(completion.telemetry, sort_keys=True)
    assert completion.payload == {"result": "valid"}
    assert completion.telemetry["http_success"] is True
    assert completion.telemetry["json_valid"] is True
    assert completion.telemetry["total_tokens"] == 25
    assert "private compact evidence" not in serialized
    assert secret not in serialized
    assert completion.telemetry["estimated_cost"] is None


def test_temporal_holdout_hash_includes_component_identity():
    from finraw.analysis.split import _component_split

    policy = {
        "temporal_holdout_pct": 10,
        "entity_holdout_pct": 0,
        "peer_scope_holdout_pct": 0,
        "signal_composition_holdout_pct": 0,
        "conflicting_evidence_holdout_pct": 0,
        "train_pct": 100,
        "dev_pct": 0,
    }
    splits = []
    for index in range(100):
        rows = [
            {
                "analysis_pattern_id": "operating_trend_summary_v1",
                "entity_ids": [f"ENTITY_{index:03d}"],
                "period_scope": {"years": [2023, 2024, 2025]},
                "signal_composition_id": "same_composition",
                "difficulty_features": {"counter_claim_count": 0},
                "scope_definition": "consolidated",
            }
        ]
        splits.append(_component_split(rows, policy))

    temporal_count = splits.count("test_temporal_holdout")
    assert 1 <= temporal_count <= 25
    assert temporal_count < len(splits)


def test_capacity_aware_split_redirects_oversized_holdout_without_splitting():
    from finraw.analysis.split import _capacity_aware_split

    split, reason = _capacity_aware_split(
        "test_temporal_holdout",
        component_size=43,
        total_sample_count=150,
        policy={
            "capacity_control_min_samples": 50,
            "maximum_holdout_component_pct": 20,
        },
    )
    assert split == "train"
    assert reason and reason.startswith("holdout_component_exceeds_capacity")

    split, reason = _capacity_aware_split(
        "test_entity_holdout",
        component_size=20,
        total_sample_count=150,
        policy={
            "capacity_control_min_samples": 50,
            "maximum_holdout_component_pct": 20,
        },
    )
    assert split == "test_entity_holdout"
    assert reason is None


def test_analysis_policy_propagates_bounded_retry_contract():
    from finraw.analysis.pipeline import _analysis_policy

    policy = _analysis_policy(
        {
            "analysis": {
                "generation": {
                    "mode": "controlled_llm",
                    "max_attempts": 3,
                    "api_quality_gate": {"maximum_retry_rate": 0.03},
                }
            }
        },
        None,
    )

    assert policy["generation"]["max_attempts"] == 3
    assert policy["generation"]["api_quality_gate"]["maximum_retry_rate"] == 0.03


def test_mixed_conclusion_surface_does_not_duplicate_mixed_modifier():
    from finraw.analysis.semantic_frames import (
        build_conclusion_semantic_frame,
        render_semantic_frame,
    )

    frame = build_conclusion_semantic_frame("mixed_growth_quality", "mixed")
    text = render_semantic_frame(frame, "conclusion_mixed", kind="conclusion")
    assert "mixed mixed" not in text.lower()
    assert "mixed growth-quality" in text.lower()
