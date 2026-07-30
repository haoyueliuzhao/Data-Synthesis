from __future__ import annotations

from typing import Any

ANSWER_SCHEMA_CONTRACT_VERSION = "answer_schema_contract.v1"

_REQUIRED_FIELDS_BY_TYPE: dict[str, tuple[str, ...]] = {
    "payload_with_source": ("payload", "source_id"),
    "comparison": ("higher_ref", "difference", "result_context"),
    "percentage": ("value", "unit"),
    "aggregate": ("method", "value"),
}


def complete_answer_schema(answer_schema: dict[str, Any]) -> dict[str, Any]:
    """Complete the public result contract from one structural registry."""

    answer_type = str(answer_schema.get("type") or "").strip()
    if not answer_type:
        raise ValueError("answer schema requires a non-empty type")
    declared = tuple(str(item) for item in answer_schema.get("required_fields") or ())
    required = tuple(dict.fromkeys((*_REQUIRED_FIELDS_BY_TYPE.get(answer_type, ()), *declared)))
    return {
        **answer_schema,
        "required_fields": list(required),
        "answer_schema_contract_version": ANSWER_SCHEMA_CONTRACT_VERSION,
    }


def required_answer_fields(answer_schema: dict[str, Any]) -> tuple[str, ...]:
    return tuple(complete_answer_schema(answer_schema)["required_fields"])


def allowed_result_fields(answer_schema: dict[str, Any]) -> set[str]:
    return set(required_answer_fields(answer_schema)) | {
        str(item) for item in answer_schema.get("optional_fields") or ()
    }
