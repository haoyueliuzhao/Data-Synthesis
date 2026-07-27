from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel

from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.core.task.schema import TaskPackage, TaskPublicSpec


class CandidateAnswerNormalizer:
    """Map public candidate answers and oracle outputs to one semantic contract."""

    def normalize_candidate(
        self, task: TaskPublicSpec, final_answer: dict[str, Any]
    ) -> dict[str, Any]:
        result = final_answer.get("result", final_answer)
        return self._normalize(task.answer_schema, result)

    def normalize_result(self, task: TaskPublicSpec, result: Any) -> dict[str, Any]:
        return self._normalize(task.answer_schema, result)

    def normalize_oracle(
        self,
        task: TaskPackage,
        oracle_output: dict[str, Any],
        gold_evidence: tuple[EvidenceItem, ...],
    ) -> dict[str, Any]:
        answer_type = str(task.public.answer_schema.get("type") or "")
        if answer_type == "payload_with_source":
            payload = oracle_output.get("payload") or {}
            source_id = gold_evidence[0].source.source_id if gold_evidence else None
            result = {"payload": payload, "source_id": source_id}
            return self._normalize(task.public.answer_schema, result)
        return self._normalize(task.public.answer_schema, oracle_output)

    def validate_schema(
        self, task: TaskPublicSpec, final_answer: dict[str, Any]
    ) -> tuple[bool, tuple[str, ...]]:
        failures: list[str] = []
        allowed_top_level = {"result", "citations"}
        if task.answer_schema.get("allow_status") is True:
            allowed_top_level.add("status")
        if task.answer_schema.get("allow_claims") is True:
            allowed_top_level.add("claims")
        unexpected = set(final_answer) - allowed_top_level
        if unexpected:
            failures.append(f"unexpected_top_level:{','.join(sorted(unexpected))}")
        result = final_answer.get("result")
        if not isinstance(result, dict):
            failures.append("result_missing_or_not_object")
            return False, tuple(failures)
        answer_type = str(task.answer_schema.get("type") or "")
        required = {
            "payload_with_source": {"source_id"},
            "comparison": {"higher_ref", "difference"},
            "percentage": {"value"},
        }.get(answer_type, set(task.answer_schema.get("required_fields") or []))
        if answer_type == "payload_with_source" and "payload" not in result:
            failures.append("payload_missing")
        missing = required - set(result)
        if missing:
            failures.append(f"required_fields_missing:{','.join(sorted(missing))}")
        allowed_result_fields = _allowed_result_fields(answer_type, result, task.answer_schema)
        unexpected_result = set(result) - allowed_result_fields
        if unexpected_result:
            failures.append(f"unexpected_result_fields:{','.join(sorted(unexpected_result))}")
        payload = result.get("payload")
        if isinstance(payload, dict):
            allowed_payload_fields = _allowed_payload_fields(task.answer_schema)
            unexpected_payload = set(payload) - allowed_payload_fields
            if unexpected_payload:
                failures.append(f"unexpected_payload_fields:{','.join(sorted(unexpected_payload))}")
        citations = final_answer.get("citations")
        if not isinstance(citations, list):
            failures.append("citations_missing_or_not_array")
        else:
            for index, citation in enumerate(citations):
                if not isinstance(citation, dict):
                    continue
                unexpected_citation = set(citation) - {
                    "evidence_id",
                    "source_id",
                    "source_locator",
                }
                if unexpected_citation:
                    failures.append(
                        "unexpected_citation_fields:"
                        f"{index}:{','.join(sorted(unexpected_citation))}"
                    )
        claims = final_answer.get("claims")
        if claims is not None and not isinstance(claims, list):
            failures.append("claims_not_array")
        return not failures, tuple(failures)

    def equivalent(self, left: dict[str, Any], right: dict[str, Any]) -> bool:
        return _canonical_value(left) == _canonical_value(right)

    def _normalize(self, answer_schema: dict[str, Any], result: Any) -> dict[str, Any]:
        if not isinstance(result, dict):
            return {"invalid_result": result}
        answer_type = str(answer_schema.get("type") or "")
        if answer_type == "comparison":
            return {
                "higher_ref": result.get("higher_ref", result.get("higher_evidence_id")),
                "difference": _decimal_string(result.get("difference")),
                "result_context": _canonical_value(answer_schema.get("result_context") or {}),
            }
        if answer_type == "percentage":
            return {"value": _decimal_string(result.get("value")), "unit": "percent"}
        if answer_type == "payload_with_source":
            return {
                "payload": _canonical_value(result.get("payload")),
                "source_id": result.get("source_id"),
            }
        return _canonical_value(result)


def _decimal_string(value: Any) -> str | None:
    if value is None:
        return None
    try:
        normalized = Decimal(str(value)).normalize()
    except (InvalidOperation, TypeError, ValueError):
        return str(value)
    return format(normalized, "f")


def _canonical_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, dict):
        return {key: _canonical_value(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    if isinstance(value, (Decimal, int, float)) and not isinstance(value, bool):
        return _decimal_string(value)
    return value


def _allowed_result_fields(
    answer_type: str,
    result: dict[str, Any],
    answer_schema: dict[str, Any],
) -> set[str]:
    if answer_type == "payload_with_source":
        return {"payload", "source_id"}
    registered = {
        "comparison": {"higher_ref", "difference", "result_context"},
        "percentage": {"value"},
        "aggregate": {"method", "value"},
    }
    return registered.get(
        answer_type,
        set(answer_schema.get("required_fields") or ()),
    ) | set(answer_schema.get("optional_fields") or ())


def _allowed_payload_fields(answer_schema: dict[str, Any]) -> set[str]:
    return set(answer_schema.get("allowed_payload_fields") or ())
