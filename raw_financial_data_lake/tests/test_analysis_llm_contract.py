from __future__ import annotations

from dataclasses import replace

from finraw.analysis.claims import build_claim_plan
from finraw.analysis.discourse import default_discourse_plan, render_analysis_text
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


def _semantic_frame_payload(plan, pattern=None):
    pattern = pattern or analysis_pattern_registry()["operating_trend_summary_v1"]
    mandatory = [claim for claim in plan.claims if claim["is_required"]]
    discourse = default_discourse_plan(mandatory, maximum_numeric_mentions=2)
    by_id = {claim["claim_id"]: claim for claim in mandatory}
    conclusion = next(
        item
        for item in plan.valid_conclusions
        if item["conclusion_id"] == plan.selected_conclusion_id
    )
    return {
        "schema_version": ANALYSIS_RESPONSE_SCHEMA_VERSION,
        "instruction_surface_form_id": "canonical",
        "selected_conclusion_id": plan.selected_conclusion_id,
        "discourse_plan": discourse,
        "claims": [
            {
                "claim_id": claim_id,
                "semantic_frame": by_id[claim_id]["semantic_frame"],
                "surface_form_id": default_surface_form_id(
                    by_id[claim_id]["semantic_frame"], kind="claim"
                ),
                "evidence_ids": by_id[claim_id]["support_signal_ids"],
                "numeric_slot_ids": discourse["selected_numeric_slot_ids"][claim_id],
            }
            for claim_id in discourse["claim_order"]
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
    assert result.generation_method == "controlled_llm_discourse_plan"
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
    validation = validate_analysis_response(invalid_payload, plan, pattern=pattern)
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

    assert result.generation_method == "controlled_llm_discourse_plan"
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
    pattern, _, plan = _operating_claim_plan()
    payload = _semantic_frame_payload(plan)
    risk_index = next(
        index
        for index, claim in enumerate(
            [claim for claim in plan.claims if claim["is_required"]]
        )
        if claim["claim_role"] == "risk"
    )
    payload["claims"][risk_index]["surface_text"] = adversarial
    assert not validate_analysis_response(payload, plan, pattern=pattern)["passed"]


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
    assert stats["valid_rewrite_rate"] == 0.0
    assert stats["valid_surface_realization_rate"] == 0.5
    assert stats["controlled_generation_rate"] == 0.5
    assert stats["fallback_rate"] == 0.5
    assert stats["fallback_reason_distribution"] == {"llm_unavailable:TimeoutError": 1}


def test_analysis_llm_gate_uses_final_attempt_validity_and_audits_raw_attempts():
    from finraw.analysis.pipeline import _analysis_llm_stats, _build_gate_failures

    sample_rows = [
        {
            "analysis_sample_id": "sample_a",
            "generation_method": "controlled_llm_discourse_plan",
            "generation_metadata": {},
        },
        {
            "analysis_sample_id": "sample_b",
            "generation_method": "controlled_llm_discourse_plan",
            "generation_metadata": {},
        },
    ]
    llm_call_rows = [
        {
            "analysis_sample_id": "sample_a",
            "attempt_index": 1,
            "is_final_attempt": False,
            "http_success": True,
            "structured_response_valid": False,
        },
        {
            "analysis_sample_id": "sample_a",
            "attempt_index": 2,
            "is_final_attempt": True,
            "http_success": True,
            "structured_response_valid": True,
        },
        {
            "analysis_sample_id": "sample_b",
            "attempt_index": 1,
            "is_final_attempt": True,
            "http_success": True,
            "structured_response_valid": True,
        },
    ]
    policy = {
        "minimum_pass_rate": 1.0,
        "minimum_pattern_samples": {},
        "generation": {
            "mode": "controlled_llm",
            "api_quality_gate": {
                "minimum_http_success_rate": 1.0,
                "minimum_structured_response_pass_rate": 1.0,
                "minimum_controlled_generation_rate": 1.0,
                "maximum_fallback_rate": 0.0,
                "maximum_retry_rate": 0.5,
            },
        },
    }

    stats = _analysis_llm_stats(sample_rows, llm_call_rows, policy)

    assert stats["request_count"] == 3
    assert stats["final_attempt_count"] == 2
    assert stats["structured_response_pass_rate"] == 1.0
    assert stats["attempt_structured_response_pass_rate"] == 2 / 3
    assert stats["retry_rate"] == 0.5
    assert not _build_gate_failures(
        {
            "pass_rate": 1.0,
            "failure_counts": {},
        },
        {},
        policy,
        stats,
    )


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


def test_discourse_plan_rejects_unknown_transition_and_claim_order_drift():
    pattern, _, plan = _operating_claim_plan()
    payload = _semantic_frame_payload(plan, pattern)
    payload["discourse_plan"]["transition_ids"][1] = "invented_transition"
    payload["claims"] = list(reversed(payload["claims"]))

    validation = validate_analysis_response(payload, plan, pattern=pattern)

    assert validation["passed"] is False
    assert "discourse_next_transition_unknown" in validation["errors"]
    assert "claim_order_discourse_mismatch" in validation["errors"]


def test_discourse_plan_rejects_unregistered_numeric_slot_and_instruction():
    pattern, _, plan = _operating_claim_plan()
    payload = _semantic_frame_payload(plan, pattern)
    claim_id = payload["claims"][0]["claim_id"]
    payload["instruction_surface_form_id"] = "invented_instruction"
    payload["discourse_plan"]["selected_numeric_slot_ids"][claim_id] = [
        "invented.numeric_slot"
    ]
    payload["claims"][0]["numeric_slot_ids"] = ["invented.numeric_slot"]

    validation = validate_analysis_response(payload, plan, pattern=pattern)

    assert validation["passed"] is False
    assert "instruction_surface_form_invalid" in validation["errors"]
    assert any(
        error.startswith("discourse_numeric_slot_invalid")
        for error in validation["errors"]
    )


def test_controlled_discourse_renders_grounded_numeric_evidence_and_instruction():
    pattern, _, plan = _operating_claim_plan()
    result = generate_analysis(
        pattern,
        plan,
        [],
        config={"mode": "controlled_llm", "maximum_numeric_mentions": 2},
        provider=_Provider(_semantic_frame_payload(plan, pattern)),
    )

    selected = [
        slot_id
        for item in result.claim_alignment
        for slot_id in item["selected_numeric_slot_ids"]
    ]
    assert result.generation_method == "controlled_llm_discourse_plan"
    assert 1 <= len(selected) <= 2
    assert result.instruction_surface_form_id == "canonical"
    assert result.instruction_text == pattern.instruction_template
    assert any(item["numeric_sentences"] for item in result.claim_alignment)
    assert validate_numeric_grounding(
        result.analysis_text,
        result.numeric_slots,
        [],
    )["passed"]

def test_discourse_renderer_avoids_duplicate_overall_and_repairs_transition_case():
    alignment = [
        {
            "claim_id": "claim_1",
            "sentence": "Revenue growth supports the assessment.",
            "numeric_sentences": [],
        }
    ]
    plan = {
        "claim_order": ["claim_1"],
        "transition_ids": ["first"],
        "style_id": "compact_evidence",
        "conclusion_transition_id": "overall",
        "caveat_transition_id": "evidence_boundary",
    }
    text = render_analysis_text(
        alignment,
        "Overall, the evidence is mixed.",
        [{"sentence": "This assessment is bounded."}],
        plan,
    )
    assert "Overall, Overall" not in text
    assert text.startswith("First, revenue growth")
    assert "Overall, the evidence is mixed." in text
    taken_together = render_analysis_text(
        alignment,
        "Taken together, the evidence is mixed.",
        [{"sentence": "This assessment is bounded."}],
        {**plan, "conclusion_transition_id": "taken_together"},
    )
    assert "Taken together, taken together" not in taken_together
    assert "Taken together, the evidence is mixed." in taken_together
    assert "Within this evidence boundary, this assessment is bounded." in text

def test_controlled_provider_can_copy_the_pinned_valid_response_template():
    pattern, signals, plan = _operating_claim_plan()

    class CapturingProvider:
        last_telemetry = {
            "provider": "fake",
            "http_success": True,
            "json_valid": True,
            "total_tokens": 10,
        }

        def __init__(self):
            self.request = None

        def generate(self, request):
            self.request = request
            return request["valid_response_template"]

    provider = CapturingProvider()
    result = generate_analysis(
        pattern,
        plan,
        signals,
        config={"mode": "controlled_llm", "maximum_numeric_mentions": 2},
        provider=provider,
    )
    assert result.generation_method == "controlled_llm_discourse_plan"
    assert provider.request is not None
    template = provider.request["valid_response_template"]
    assert set(template) == {
        "schema_version",
        "instruction_surface_form_id",
        "selected_conclusion_id",
        "discourse_plan",
        "claims",
        "conclusion_semantic_frame",
        "conclusion_surface_form_id",
        "caveats",
    }
    assert len(provider.request["numeric_slots"]) <= len(result.numeric_slots)
