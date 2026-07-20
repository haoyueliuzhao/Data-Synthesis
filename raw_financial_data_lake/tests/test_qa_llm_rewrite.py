from __future__ import annotations

import io
import json
import urllib.error
import urllib.request

from finraw.llm_client import OpenAICompatibleJsonClient
from finraw.qa.verbalizer import (
    QUESTION_REWRITE_VERSION,
    build_protected_question,
    diversify_surface_slots,
    realize_question,
    surface_variation_manifest,
)


class _RewriteProvider:
    def __init__(self, payload):
        self.payload = payload
        self.requests = []
        self.last_telemetry = {
            "http_success": True,
            "json_valid": True,
            "response_model": "test-model",
        }

    def generate(self, request):
        self.requests.append(request)
        return self.payload if isinstance(self.payload, list) else [self.payload]


def _rewrite_case(provider, *, style_variant_id="analyst"):
    canonical = (
        "Within Technology, filter companies whose Revenue growth exceeded 10% "
        "in 2023, then rank the top 3 by net margin."
    )
    slots = {
        "scope": "Technology",
        "growth_metric": "Revenue",
        "growth_threshold": "10",
        "period": "2023",
        "top_k": "3",
        "ranking_metric": "net margin",
    }
    semantics = {
        "time_scope": {"basis": "fiscal_year"},
        "operation_plan": {
            "operators": [
                {
                    "step_id": "screen",
                    "operator": "filter",
                    "params": {"comparison": "gt", "value": "10"},
                },
                {
                    "step_id": "rank",
                    "operator": "rank",
                    "params": {"direction": "desc", "top_k": 3},
                },
            ]
        },
    }
    surface = {
        **slots,
        "growth_metric": "sales",
        "period": "FY2023",
        "ranking_metric": "net profit margin",
    }
    protected = build_protected_question(
        (
            "Within {scope}, filter companies whose {growth_metric} growth exceeded "
            "{growth_threshold}% in {period}, then rank the top {top_k} by "
            "{ranking_metric}."
        ),
        list(slots),
    )
    return realize_question(
        canonical,
        semantics=semantics,
        immutable_slots=slots,
        required_slots=list(slots),
        config={
            "mode": "controlled_llm",
            "strategy": "protected_rewrite",
            "variants": 2,
            "style_variant_id": style_variant_id,
        },
        provider=provider,
        surface_slots=surface,
        protected_question=protected,
    )


def test_protected_api_rewrite_changes_language_but_preserves_surface_slots():
    provider = _RewriteProvider(
        {
            "rewrite_version": QUESTION_REWRITE_VERSION,
            "question_template": (
                "For <slot_period> within <slot_scope>, first screen businesses with "
                "<slot_growth_metric> growth above <slot_growth_threshold>%; then "
                "identify the top <slot_top_k> by <slot_ranking_metric>?"
            ),
        }
    )
    result = _rewrite_case(provider)

    assert result.generation_method == "controlled_llm_protected_rewrite"
    assert result.validation["passed"] is True
    assert "sales growth above 10%" in result.question
    assert "FY2023" in result.question
    assert "net profit margin" in result.question
    request = provider.requests[0]
    serialized = json.dumps(request)
    assert request["generation_strategy"] == "protected_rewrite"
    assert request["style_variant_id"] == "analyst"
    assert "analyst-review" in request["style_instruction"]
    assert result.validation["style_variant_id"] == "analyst"
    assert "Technology" not in serialized
    assert "Revenue" not in serialized
    assert "2023" not in serialized
    assert "answer" not in serialized.casefold()


def test_protected_rewrite_rejects_comparison_reversal_and_falls_back():
    provider = _RewriteProvider(
        {
            "rewrite_version": QUESTION_REWRITE_VERSION,
            "question_template": (
                "Within <slot_scope>, screen businesses with <slot_growth_metric> "
                "growth below <slot_growth_threshold>% in <slot_period>, then rank "
                "the top <slot_top_k> by <slot_ranking_metric>?"
            ),
        }
    )
    result = _rewrite_case(provider)

    assert result.generation_method == "deterministic_surface_fallback"
    assert result.validation["rewrite_valid"] is False
    assert (
        "question_semantics:filter_comparison_mismatch"
        in result.validation["rewrite_errors"]
    )


def test_protected_rewrite_rejects_unprotected_numbers_and_extra_claims():
    provider = _RewriteProvider(
        {
            "rewrite_version": QUESTION_REWRITE_VERSION,
            "question_template": (
                "Within <slot_scope>, screen 50 businesses by <slot_growth_metric> "
                "above <slot_growth_threshold>% in <slot_period>, then rank the top "
                "<slot_top_k> by <slot_ranking_metric> because management quality is poor?"
            ),
        }
    )
    result = _rewrite_case(provider)

    assert result.generation_method == "deterministic_surface_fallback"
    assert "rewrite_unprotected_number" in result.validation["rewrite_errors"]
    assert "rewrite_forbidden_extension" in result.validation["rewrite_errors"]


def test_surface_variation_is_deterministic_and_manifested():
    slots = {
        "entity": "Apple Inc.",
        "metric": "Revenue",
        "period": "2023",
    }
    policy = {
        "surface_variation": {
            "enabled": True,
            "entity_suffix_shortening": True,
        }
    }
    first = diversify_surface_slots(
        slots, {"time_scope": {"basis": "fiscal_year"}}, "stable", policy
    )
    second = diversify_surface_slots(
        slots, {"time_scope": {"basis": "fiscal_year"}}, "stable", policy
    )

    assert first == second
    assert first["entity"] in {"Apple Inc.", "Apple"}
    assert first["metric"] in {"Revenue", "revenue", "sales"}
    assert first["period"] in {"2023", "FY2023"}
    assert surface_variation_manifest(policy)["surface_variation_manifest_hash"]


def test_llm_client_discovers_models_and_falls_back_on_model_quota(monkeypatch):
    monkeypatch.setenv("FINRAW_TEST_API_KEY", "secret")
    post_models = []

    class Response:
        status = 200

        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return json.dumps(self.payload).encode()

    def fake_urlopen(request, timeout):
        if request.get_method() == "GET":
            return Response(
                {
                    "data": [
                        {"id": "text-embedding-v4"},
                        {"id": "qwen-plus"},
                        {"id": "qwen-turbo"},
                    ]
                }
            )
        body = json.loads(request.data.decode())
        post_models.append(body["model"])
        if body["model"] == "qwen-turbo":
            raise urllib.error.HTTPError(
                request.full_url,
                429,
                "quota exhausted",
                {},
                io.BytesIO(b""),
            )
        return Response(
            {
                "id": "response",
                "model": body["model"],
                "choices": [{"message": {"content": json.dumps({"rewrites": []})}}],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 2,
                    "total_tokens": 12,
                },
            }
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    client = OpenAICompatibleJsonClient(
        {
            "endpoint": "https://example.test/v1/chat/completions",
            "model": "qwen-turbo",
            "fallback_models": ["qwen-plus"],
            "auto_select_model": True,
            "maximum_model_attempts": 3,
            "api_key_env": "FINRAW_TEST_API_KEY",
        }
    )
    completion = client.complete_json("protected prompt")

    assert post_models == ["qwen-turbo", "qwen-plus"]
    assert completion.telemetry["response_model"] == "qwen-plus"
    assert completion.telemetry["model_fallback_used"] is True
    assert completion.telemetry["model_attempt_count"] == 2
    assert completion.telemetry["model_discovery"]["discovered_model_count"] == 3
    assert completion.telemetry["attempted_models"] == ["qwen-turbo", "qwen-plus"]
    serialized = json.dumps(completion.telemetry)
    assert "protected prompt" not in serialized
    assert "secret" not in serialized

def test_protected_rewrite_selects_a_stable_variant_by_style_id():
    templates = [
        {
            "rewrite_version": QUESTION_REWRITE_VERSION,
            "question_template": (
                "Within <slot_scope>, filter companies whose <slot_growth_metric> "
                "growth exceeded <slot_growth_threshold>% in <slot_period>, then "
                "rank the top <slot_top_k> by <slot_ranking_metric>?"
            ),
        },
        {
            "rewrite_version": QUESTION_REWRITE_VERSION,
            "question_template": (
                "For <slot_period> in <slot_scope>, identify businesses with "
                "<slot_growth_metric> growth above <slot_growth_threshold>%, then "
                "list the top <slot_top_k> by <slot_ranking_metric>?"
            ),
        },
    ]
    provider = _RewriteProvider(templates)
    result = _rewrite_case(provider, style_variant_id="comparative")
    assert result.generation_method == "controlled_llm_protected_rewrite"
    assert result.validation["rewrite_variant_index"] == 1
    assert result.question.startswith("For FY2023")
