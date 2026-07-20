from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Protocol

from finraw.llm_client import LLMClientError, OpenAICompatibleJsonClient
from finraw.qa.graph_patterns import pattern_manifest
from finraw.qa.graph_walk.operation_macros import operation_macro_manifest
from finraw.qa.operators import operator_registry


PATTERN_IDEATION_VERSION = "pattern_ideation.v1"
INTENT_FAMILIES = {
    "comparison",
    "temporal_investigation",
    "scope_screening",
    "multi_stage_followup",
    "provenance",
    "consistency_check",
}
NOVELTY_AXES = {
    "metric_pair",
    "time_window",
    "scope",
    "operation_composition",
    "answer_form",
    "evidence_trace",
}


class PatternIdeaProvider(Protocol):
    def generate(self, request: dict[str, Any]) -> list[Any]: ...


class OpenAICompatiblePatternIdeaProvider:
    def __init__(self, config: dict[str, Any]):
        self.client = OpenAICompatibleJsonClient(config)
        self.last_telemetry: dict[str, Any] = {}

    def generate(self, request: dict[str, Any]) -> list[Any]:
        prompt = (
            "Act only as a financial QA pattern ideation advisor. Select an existing "
            "base_pattern_id and only the supplied metric IDs, intent families, novelty "
            "axes, and executable operator IDs. Do not invent facts, answers, graph "
            "relations, operators, metrics, thresholds, or source definitions. Ideas are "
            "advisory and will still require deterministic KG compilation and verification. "
            "Return JSON only as "
            '{"pattern_ideas":[{"idea_version":"pattern_ideation.v1",'
            '"base_pattern_id":"...","metric_ids":["..."],'
            '"intent_family":"...","novelty_axis":"...","rationale":"..."}]}'
            "\n" + json.dumps(request, ensure_ascii=False, sort_keys=True)
        )
        try:
            completion = self.client.complete_json(prompt, temperature=0.6)
        except LLMClientError as exc:
            self.last_telemetry = dict(exc.telemetry)
            raise
        ideas = [
            item
            for item in completion.payload.get("pattern_ideas") or []
            if isinstance(item, dict)
        ]
        self.last_telemetry = {
            **completion.telemetry,
            "structured_item_count": len(ideas),
        }
        return ideas


def generate_pattern_ideas(
    metric_ids: list[str],
    config: dict[str, Any],
    *,
    provider: PatternIdeaProvider | None = None,
) -> dict[str, Any]:
    policy = dict(config or {})
    allowed_metrics = sorted(set(str(item) for item in metric_ids if str(item)))
    base_patterns = sorted(
        {
            str(item["pattern_id"])
            for item in pattern_manifest()
            if item.get("is_active", True)
        }
        | {str(item["macro_id"]) for item in operation_macro_manifest()["macros"]}
    )
    allowed_operators = sorted(operator_registry())
    request = {
        "idea_version": PATTERN_IDEATION_VERSION,
        "base_pattern_ids": base_patterns,
        "metric_ids": allowed_metrics,
        "intent_families": sorted(INTENT_FAMILIES),
        "novelty_axes": sorted(NOVELTY_AXES),
        "operator_ids": allowed_operators,
        "maximum_ideas": max(int(policy.get("maximum_ideas", 10)), 1),
    }
    effective_provider = provider or OpenAICompatiblePatternIdeaProvider(
        policy.get("llm") or {}
    )
    raw = effective_provider.generate(request)
    accepted = []
    rejected = []
    for item in raw:
        validation = validate_pattern_idea(
            item,
            base_pattern_ids=set(base_patterns),
            metric_ids=set(allowed_metrics),
        )
        target = accepted if validation["passed"] else rejected
        target.append({**validation, "idea": item})
    accepted = accepted[: request["maximum_ideas"]]
    manifest = {
        "pattern_ideation_version": PATTERN_IDEATION_VERSION,
        "base_pattern_ids": base_patterns,
        "operator_ids": allowed_operators,
        "intent_families": sorted(INTENT_FAMILIES),
        "novelty_axes": sorted(NOVELTY_AXES),
    }
    manifest_hash = hashlib.sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "mode": "advisory_only",
        "requires_deterministic_compilation": True,
        "manifest": {**manifest, "manifest_hash": manifest_hash},
        "request_metric_count": len(allowed_metrics),
        "accepted_ideas": [item["idea"] for item in accepted],
        "rejected_ideas": rejected,
        "telemetry": dict(getattr(effective_provider, "last_telemetry", {}) or {}),
    }


def write_pattern_ideation_report(
    report: dict[str, Any], output_dir: str | Path
) -> Path:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    output = target / "qa_pattern_ideation_report.json"
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return output


def validate_pattern_idea(
    idea: Any,
    *,
    base_pattern_ids: set[str],
    metric_ids: set[str],
) -> dict[str, Any]:
    if not isinstance(idea, dict):
        return {"passed": False, "errors": ["idea_not_object"]}
    errors = []
    allowed_fields = {
        "idea_version",
        "base_pattern_id",
        "metric_ids",
        "intent_family",
        "novelty_axis",
        "rationale",
    }
    if set(idea) - allowed_fields:
        errors.append("idea_unknown_fields")
    if str(idea.get("idea_version") or "") != PATTERN_IDEATION_VERSION:
        errors.append("idea_version_invalid")
    if str(idea.get("base_pattern_id") or "") not in base_pattern_ids:
        errors.append("idea_base_pattern_unknown")
    proposed_metrics = {str(item) for item in idea.get("metric_ids") or [] if str(item)}
    if not proposed_metrics or not proposed_metrics <= metric_ids:
        errors.append("idea_metric_ids_invalid")
    if str(idea.get("intent_family") or "") not in INTENT_FAMILIES:
        errors.append("idea_intent_family_invalid")
    if str(idea.get("novelty_axis") or "") not in NOVELTY_AXES:
        errors.append("idea_novelty_axis_invalid")
    rationale = str(idea.get("rationale") or "").strip()
    if not rationale or len(rationale) > 240:
        errors.append("idea_rationale_invalid")
    return {"passed": not errors, "errors": errors}
