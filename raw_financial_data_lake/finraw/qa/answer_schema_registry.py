from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any


ANSWER_SCHEMA_REGISTRY_VERSION = "qa_answer_schema_registry.v1"

SUPPORTED_ANSWER_TYPES = frozenset(
    {
        "numeric",
        "comparison",
        "period_and_value",
        "period_metric_lookup",
        "period_metric_provenance",
        "ranked_table",
        "multi_metric_ranked_table",
        "screening_table",
        "filtered_rank_followup",
    }
)


def resolve_answer_schema(
    answer_type: str,
    candidate_schema: dict[str, Any] | None,
    rubric: dict[str, Any],
    canonical_semantics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    schema = dict(candidate_schema or {})
    schema_type = str(schema.get("type") or answer_type)
    if schema_type != answer_type:
        raise ValueError(
            f"Answer schema type mismatch: sample={answer_type}, candidate={schema_type}"
        )
    if schema_type not in SUPPORTED_ANSWER_TYPES:
        raise ValueError(f"Unsupported answer schema: {schema_type}")
    schema["type"] = schema_type
    schema["registry_version"] = ANSWER_SCHEMA_REGISTRY_VERSION
    schema["requested_unit"] = rubric.get("requested_unit")
    schema["requested_currency"] = rubric.get("requested_currency")
    schema["order_required"] = bool(rubric.get("order_required"))
    schema["value_tolerance"] = str(
        rubric.get("value_tolerance")
        or rubric.get("absolute_tolerance")
        or "0.000001"
    )
    canonical = dict(canonical_semantics or {})
    if schema_type == "filtered_rank_followup":
        schema["top_k"] = int(schema.get("top_k") or 3)
        schema["followup_rank"] = int(schema.get("followup_rank") or 1)
        schema["thresholds"] = canonical.get("thresholds") or {
            key: rubric[key]
            for key in sorted(rubric)
            if key.endswith("_threshold_pct") or key.endswith("_max_pct")
        }
        schema["scope"] = canonical.get("scope") or canonical.get("entity_scope") or {}
    elif schema_type == "screening_table":
        schema["filter_metadata"] = {
            key: rubric[key]
            for key in sorted(rubric)
            if key.endswith("_pct")
        }
    return schema


def model_contract(schema: dict[str, Any]) -> dict[str, Any]:
    unit = schema.get("requested_unit") or "unit stated in question"
    currency = schema.get("requested_currency") or None
    answer_type = str(schema["type"])
    if answer_type == "numeric":
        payload = {"value": "numeric string", "unit": unit, "currency": currency}
    elif answer_type == "comparison":
        payload = {
            "winner_id": "exact evidence entity_id or metric_id",
            "relation": "greater, less, or equal",
            "difference": "non-negative numeric string",
            "rows": [{"id": "entity_id or metric_id", "value": "numeric string"}],
            "unit": unit,
            "currency": currency,
        }
    elif answer_type == "period_and_value":
        payload = {
            "result_period": "year, quarter, month, or date",
            "value": "numeric string",
            "unit": unit,
            "currency": currency,
        }
    elif answer_type in {"period_metric_lookup", "period_metric_provenance"}:
        payload = {
            "result_period": "selected period",
            "primary_value": "numeric string",
            "secondary_value": "numeric string",
            "primary_unit": unit,
            "secondary_unit": unit,
            "currency": currency,
        }
        if answer_type == "period_metric_provenance":
            payload["raw_object_ids"] = ["exact raw_object_id"]
    elif answer_type == "ranked_table":
        payload = {
            "ranking_table": [
                {
                    "rank": "integer",
                    "entity_id": "exact entity_id",
                    "value": "numeric string",
                }
            ],
            "unit": unit,
            "currency": currency,
        }
    elif answer_type == "multi_metric_ranked_table":
        payload = {
            "ranking_table": [
                {
                    "rank": "integer",
                    "entity_id": "exact entity_id",
                    "value": "primary metric numeric string",
                }
            ],
            "secondary_metric_table": [
                {
                    "rank": "integer",
                    "entity_id": "exact entity_id",
                    "value": "secondary metric numeric string",
                }
            ],
            "primary_unit": unit,
            "secondary_unit": unit,
            "currency": currency,
        }
    elif answer_type == "filtered_rank_followup":
        payload = {
            "ranking_table": [
                {
                    "rank": "integer",
                    "entity_id": "exact entity_id",
                    "value": "ranking metric numeric string",
                }
            ],
            "followup_table": [
                {
                    "rank": int(schema["followup_rank"]),
                    "entity_id": "exact entity_id at followup rank",
                    "value": "follow-up metric numeric string",
                }
            ],
            "metadata": {
                "top_k": int(schema["top_k"]),
                "followup_rank": int(schema["followup_rank"]),
                "thresholds": schema.get("thresholds") or {},
                "scope": schema.get("scope") or {},
            },
            "primary_unit": unit,
            "secondary_unit": unit,
            "currency": currency,
        }
    elif answer_type == "screening_table":
        payload = {
            "screening_table": [
                {
                    "entity_id": "exact entity_id",
                    "revenue_growth_pct": "numeric string",
                    "net_margin_pct": "numeric string",
                    "debt_ratio_pct": "numeric string",
                }
            ],
            "filter_metadata": schema.get("filter_metadata") or {},
            "unit": unit,
            "currency": currency,
        }
    else:
        raise ValueError(f"Unsupported answer schema: {answer_type}")
    return {
        "answer_text": "brief human-readable final answer in the question language",
        "answer_payload": payload,
        "answer_schema_registry_version": ANSWER_SCHEMA_REGISTRY_VERSION,
    }


def rubric_contract(
    schema: dict[str, Any], rubric: dict[str, Any]
) -> dict[str, Any]:
    return {
        "answer_schema_registry_version": ANSWER_SCHEMA_REGISTRY_VERSION,
        "answer_schema_type": schema["type"],
        "match_type": rubric.get("match_type") or schema["type"],
        "order_required": bool(schema.get("order_required")),
        "unit_must_match": bool(rubric.get("unit_must_match")),
        "requested_unit": schema.get("requested_unit"),
        "requested_currency": schema.get("requested_currency"),
        "value_tolerance": schema.get("value_tolerance"),
        "complete_output_required": bool(
            rubric.get("complete_output_required")
        ),
    }


def normalize_model_answer(
    payload: dict[str, Any], schema: dict[str, Any]
) -> tuple[str, dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError("Model answer must be a JSON object")
    answer_text = str(payload.get("answer_text") or "").strip()
    answer_payload = payload.get("answer_payload")
    if not answer_text or not isinstance(answer_payload, dict):
        raise ValueError("Model answer requires answer_text and answer_payload")
    answer_type = str(schema["type"])
    if answer_type == "numeric" and _decimal(answer_payload.get("value")) is None:
        raise ValueError("numeric answer_payload.value must be numeric")
    required_lists = {
        "ranked_table": ("ranking_table",),
        "multi_metric_ranked_table": (
            "ranking_table",
            "secondary_metric_table",
        ),
        "screening_table": ("screening_table",),
        "filtered_rank_followup": ("ranking_table", "followup_table"),
    }.get(answer_type, ())
    for field in required_lists:
        if not isinstance(answer_payload.get(field), list):
            raise ValueError(f"{answer_type} requires answer_payload.{field}")
    if answer_type == "filtered_rank_followup" and not isinstance(
        answer_payload.get("metadata"), dict
    ):
        raise ValueError(
            "filtered_rank_followup requires answer_payload.metadata"
        )
    if answer_type == "screening_table" and not isinstance(
        answer_payload.get("filter_metadata"), dict
    ):
        raise ValueError("screening_table requires answer_payload.filter_metadata")
    return answer_text, answer_payload


def match_answer(
    schema: dict[str, Any],
    expected: dict[str, Any],
    observed: dict[str, Any],
    rubric: dict[str, Any],
) -> tuple[bool, dict[str, Any]]:
    answer_type = str(schema["type"])
    expected = canonical_gold(schema, expected, rubric)
    checks: dict[str, bool] = {}
    if answer_type == "numeric":
        return _match_numeric(expected, observed, rubric)
    if answer_type == "comparison":
        checks["winner"] = str(observed.get("winner_id")) == str(
            rubric.get("winner_id") or expected.get("winner_id")
        )
        checks["relation"] = str(observed.get("relation")) == str(
            rubric.get("relation") or expected.get("relation")
        )
        checks["difference"] = _numeric_field_match(
            rubric.get("difference") or expected.get("difference"),
            observed.get("difference"),
            rubric,
        )
        checks["rows"] = _table_match(
            rubric.get("target_rows") or expected.get("rows") or [],
            observed.get("rows") or [],
            rubric,
        )
    elif answer_type == "period_and_value":
        checks["period"] = _period_match(
            rubric.get("target_period") or expected.get("result_period"), observed
        )
        checks["value"] = _numeric_field_match(
            rubric.get("target_value") or expected.get("value"),
            observed.get("value"),
            rubric,
        )
    elif answer_type in {"period_metric_lookup", "period_metric_provenance"}:
        checks["period"] = _period_match(
            rubric.get("target_period")
            or expected.get("result_period")
            or expected.get("period"),
            observed,
        )
        checks["primary_value"] = _numeric_field_match(
            rubric.get("primary_value") or expected.get("primary_value"),
            observed.get("primary_value"),
            rubric,
        )
        checks["secondary_value"] = _numeric_field_match(
            rubric.get("secondary_value")
            or expected.get("secondary_value")
            or expected.get("value"),
            observed.get("secondary_value")
            if observed.get("secondary_value") is not None
            else observed.get("value"),
            rubric,
        )
        if answer_type == "period_metric_provenance":
            checks["raw_object_ids"] = set(
                str(item) for item in expected.get("raw_object_ids") or []
            ) == set(str(item) for item in observed.get("raw_object_ids") or [])
    elif answer_type == "ranked_table":
        checks["ranking_table"] = _table_match(
            expected["ranking_table"],
            observed.get("ranking_table") or [],
            rubric,
        )
    elif answer_type == "multi_metric_ranked_table":
        checks["ranking_table"] = _table_match(
            expected["ranking_table"],
            observed.get("ranking_table") or [],
            rubric,
        )
        checks["secondary_metric_table"] = _table_match(
            expected["secondary_metric_table"],
            observed.get("secondary_metric_table") or [],
            rubric,
        )
    elif answer_type == "filtered_rank_followup":
        checks["ranking_table"] = _table_match(
            expected["ranking_table"],
            observed.get("ranking_table") or [],
            rubric,
        )
        checks["followup_table"] = _table_match(
            expected["followup_table"],
            observed.get("followup_table") or [],
            rubric,
        )
        checks["metadata"] = _metadata_match(
            expected["metadata"], observed.get("metadata") or {}
        )
    elif answer_type == "screening_table":
        checks["screening_table"] = _table_match(
            expected["screening_table"],
            observed.get("screening_table") or [],
            rubric,
        )
        checks["filter_metadata"] = _metadata_match(
            expected["filter_metadata"],
            observed.get("filter_metadata") or {},
        )
    else:
        return False, {"reason": f"unsupported_answer_type:{answer_type}"}
    checks["unit"] = _unit_contract_match(expected, observed, rubric)
    return all(checks.values()), {
        "answer_schema_registry_version": ANSWER_SCHEMA_REGISTRY_VERSION,
        "answer_schema_type": answer_type,
        "checks": checks,
    }


def canonical_gold(
    schema: dict[str, Any], expected: dict[str, Any], rubric: dict[str, Any]
) -> dict[str, Any]:
    answer_type = str(schema["type"])
    out = dict(expected or {})
    target_answer = rubric.get("target_answer")
    if isinstance(target_answer, dict):
        out = {**out, **target_answer}
    rows = rubric.get("target_rows")
    if rows is None:
        rows = out.get("table") or []
    if answer_type == "ranked_table":
        out["ranking_table"] = out.get("ranking_table") or rows
    elif answer_type == "multi_metric_ranked_table":
        source_rows = out.get("table") or rows
        out["ranking_table"] = out.get("ranking_table") or [
            {
                "rank": row.get("rank"),
                "entity_id": row.get("entity_id"),
                "value": row.get("primary_value"),
            }
            for row in source_rows
        ]
        out["secondary_metric_table"] = [
            {
                "rank": row.get("rank"),
                "entity_id": row.get("entity_id"),
                "value": row.get("secondary_value"),
            }
            for row in source_rows
        ]
    elif answer_type == "filtered_rank_followup":
        source_rows = out.get("table") or rows
        out["ranking_table"] = out.get("ranking_table") or [
            {
                "rank": row.get("rank"),
                "entity_id": row.get("entity_id"),
                "value": row.get("primary_value"),
            }
            for row in source_rows
        ]
        followup_rank = int(schema.get("followup_rank") or 1)
        out["followup_table"] = [
            {
                "rank": row.get("rank"),
                "entity_id": row.get("entity_id"),
                "value": row.get("secondary_value"),
            }
            for row in source_rows
            if int(row.get("rank") or 0) == followup_rank
        ]
        out["metadata"] = {
            "top_k": int(schema.get("top_k") or len(out["ranking_table"])),
            "followup_rank": followup_rank,
            "thresholds": schema.get("thresholds") or {},
            "scope": schema.get("scope") or {},
        }
    elif answer_type == "screening_table":
        out["screening_table"] = rows
        out["filter_metadata"] = schema.get("filter_metadata") or {}
    return out


def render_answer(
    schema: dict[str, Any], payload: dict[str, Any], language: str = "en"
) -> str:
    answer_type = str(schema["type"])
    if answer_type == "numeric":
        return _value_with_unit(payload.get("value"), payload.get("unit"))
    if answer_type == "comparison":
        winner = payload.get("winner_id")
        difference = _value_with_unit(
            payload.get("difference"), payload.get("unit")
        )
        return (
            f"{winner} is higher by {difference}."
            if language != "zh"
            else f"{winner}: {difference}"
        )
    if answer_type.startswith("period_"):
        period = payload.get("result_period") or payload.get("period")
        value = payload.get("secondary_value", payload.get("value"))
        return f"{period}: {_value_with_unit(value, payload.get('unit'))}"
    table_field = {
        "ranked_table": "ranking_table",
        "multi_metric_ranked_table": "ranking_table",
        "filtered_rank_followup": "ranking_table",
        "screening_table": "screening_table",
    }.get(answer_type)
    if table_field:
        return json.dumps(
            payload.get(table_field) or [], ensure_ascii=False, separators=(",", ":")
        )
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def answer_schema_manifest() -> dict[str, Any]:
    manifest = {
        "version": ANSWER_SCHEMA_REGISTRY_VERSION,
        "supported_answer_types": sorted(SUPPORTED_ANSWER_TYPES),
        "complex_sections": {
            "multi_metric_ranked_table": [
                "ranking_table",
                "secondary_metric_table",
            ],
            "filtered_rank_followup": [
                "ranking_table",
                "followup_table",
                "metadata",
            ],
            "screening_table": ["screening_table", "filter_metadata"],
        },
    }
    manifest["manifest_hash"] = hashlib.sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return manifest


def _match_numeric(
    expected: dict[str, Any], observed: dict[str, Any], rubric: dict[str, Any]
) -> tuple[bool, dict[str, Any]]:
    target = _decimal(rubric.get("target_value")) or _decimal(expected.get("value"))
    value = _decimal(observed.get("value"))
    if target is None or value is None:
        return False, {"reason": "missing_numeric_value"}
    tolerance = _numeric_tolerance(target, rubric)
    candidates = [value]
    if rubric.get("accept_percent_decimal_equivalence"):
        candidates.extend([value * Decimal("100"), value / Decimal("100")])
    error = min(abs(target - candidate) for candidate in candidates)
    unit_expected = str(
        rubric.get("requested_unit") or expected.get("unit") or ""
    ).strip()
    unit_observed = str(observed.get("unit") or "").strip()
    currency_expected = str(
        rubric.get("requested_currency") or expected.get("currency") or ""
    ).strip()
    currency_observed = str(observed.get("currency") or "").strip()
    unit_ok = not rubric.get("unit_must_match") or _same_token(
        unit_expected, unit_observed
    )
    currency_ok = not currency_expected or _same_token(
        currency_expected, currency_observed
    )
    return error <= tolerance and unit_ok and currency_ok, {
        "answer_schema_registry_version": ANSWER_SCHEMA_REGISTRY_VERSION,
        "numeric_error": str(error),
        "tolerance": str(tolerance),
        "unit_match": unit_ok,
        "currency_match": currency_ok,
    }


def _numeric_tolerance(target: Decimal, rubric: dict[str, Any]) -> Decimal:
    absolute = max(
        (_decimal(rubric.get(key)) or Decimal("0"))
        for key in (
            "absolute_tolerance",
            "value_tolerance",
            "display_absolute_tolerance",
        )
    )
    places = rubric.get("requested_decimal_places")
    if places is not None:
        absolute = max(
            absolute, Decimal("0.5") * Decimal("1").scaleb(-int(places))
        )
    relative = _decimal(rubric.get("relative_tolerance")) or Decimal("0")
    return max(absolute, abs(target) * relative, Decimal("0.000001"))


def _numeric_field_match(
    expected: Any, observed: Any, rubric: dict[str, Any]
) -> bool:
    target = _decimal(expected)
    value = _decimal(observed)
    if target is None or value is None:
        return False
    candidates = [value]
    if rubric.get("accept_percent_decimal_equivalence"):
        candidates.extend([value * Decimal("100"), value / Decimal("100")])
    return min(abs(target - item) for item in candidates) <= _numeric_tolerance(
        target, rubric
    )


def _table_match(
    expected_rows: list[dict[str, Any]],
    observed_rows: list[dict[str, Any]],
    rubric: dict[str, Any],
) -> bool:
    if len(expected_rows) != len(observed_rows):
        return False

    def row_matches(
        expected_row: dict[str, Any], observed_row: dict[str, Any]
    ) -> bool:
        if not isinstance(observed_row, dict):
            return False
        for key, expected_value in expected_row.items():
            observed_value = observed_row.get(key)
            if _decimal(expected_value) is not None:
                if not _numeric_field_match(expected_value, observed_value, rubric):
                    return False
            elif str(expected_value) != str(observed_value):
                return False
        return True

    if rubric.get("order_required"):
        return all(
            row_matches(expected_row, observed_row)
            for expected_row, observed_row in zip(expected_rows, observed_rows)
        )
    unmatched = list(observed_rows)
    for expected_row in expected_rows:
        match_index = next(
            (
                index
                for index, observed_row in enumerate(unmatched)
                if row_matches(expected_row, observed_row)
            ),
            None,
        )
        if match_index is None:
            return False
        unmatched.pop(match_index)
    return not unmatched


def _metadata_match(expected: Any, observed: Any) -> bool:
    return json.dumps(expected, sort_keys=True, default=str) == json.dumps(
        observed, sort_keys=True, default=str
    )


def _period_match(expected: Any, observed: dict[str, Any]) -> bool:
    actual = observed.get("result_period")
    if actual is None:
        actual = observed.get("period")
    expected_text = str(expected).strip()
    actual_text = str(actual).strip()
    if expected_text == actual_text:
        return True
    if re.fullmatch(r"(?:19|20)\d{2}", expected_text):
        years = re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", actual_text)
        return years == [expected_text]
    return False


def _unit_contract_match(
    expected: dict[str, Any], observed: dict[str, Any], rubric: dict[str, Any]
) -> bool:
    if not rubric.get("unit_must_match"):
        return True
    requested = str(rubric.get("requested_unit") or expected.get("unit") or "")
    candidates = [
        observed.get("unit"),
        observed.get("primary_unit"),
        observed.get("secondary_unit"),
    ]
    return any(_same_token(requested, str(item or "")) for item in candidates)


def _same_token(left: str, right: str) -> bool:
    def normalize(value: str) -> str:
        return re.sub(r"[^a-z0-9%]+", "", value.casefold())

    return normalize(left) == normalize(right)


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return None


def _value_with_unit(value: Any, unit: Any) -> str:
    return (str(value or "") + (" " + str(unit) if unit else "")).strip()
