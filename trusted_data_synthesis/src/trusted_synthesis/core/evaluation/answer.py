from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel

from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.core.task.answer_schema import (
    allowed_result_fields,
    required_answer_fields,
)
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
        *,
        node_outputs: Mapping[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        answer_type = str(task.public.answer_schema.get("type") or "")
        if answer_type == "payload_with_source":
            payload = oracle_output.get("payload") or {}
            source_id = gold_evidence[0].source.source_id if gold_evidence else None
            result = {"payload": payload, "source_id": source_id}
            return self._normalize(task.public.answer_schema, result)
        if answer_type == "comparison":
            result = {
                **oracle_output,
                "result_context": task.public.answer_schema["result_context"],
            }
            return self._normalize(task.public.answer_schema, result)
        if answer_type == "percentage":
            result = {
                **oracle_output,
                "unit": task.public.answer_schema["unit"],
            }
            return self._normalize(task.public.answer_schema, result)
        if answer_type == "derived_growth_comparison":
            return self._normalize_labeled_comparison(
                task,
                oracle_output,
                node_outputs or {},
            )
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
        required = set(required_answer_fields(task.answer_schema))
        missing = required - set(result)
        if missing:
            failures.append(f"required_fields_missing:{','.join(sorted(missing))}")
        allowed_fields = allowed_result_fields(task.answer_schema)
        unexpected_result = set(result) - allowed_fields
        if unexpected_result:
            failures.append(f"unexpected_result_fields:{','.join(sorted(unexpected_result))}")
        payload = result.get("payload")
        if isinstance(payload, dict):
            allowed_payload_fields = _allowed_payload_fields(task.answer_schema)
            unexpected_payload = set(payload) - allowed_payload_fields
            if unexpected_payload:
                failures.append(f"unexpected_payload_fields:{','.join(sorted(unexpected_payload))}")
        for field in required:
            if field in task.answer_schema and field in result:
                expected = _canonical_value(task.answer_schema[field])
                observed = _canonical_value(result[field])
                if observed != expected:
                    failures.append(f"answer_schema_constant_mismatch:{field}")
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
                "result_context": _canonical_value(result.get("result_context")),
            }
        if answer_type == "percentage":
            return {
                "value": _decimal_string(result.get("value")),
                "unit": result.get("unit"),
            }
        if answer_type == "payload_with_source":
            return {
                "payload": _canonical_value(result.get("payload")),
                "source_id": result.get("source_id"),
            }
        if answer_type == "derived_growth_comparison":
            return {
                "selected_entity_id": result.get("selected_entity_id"),
                "selected_entity_name": result.get("selected_entity_name"),
                "left_entity_id": result.get("left_entity_id"),
                "left_entity_name": result.get("left_entity_name"),
                "left_growth_pct": _decimal_string(result.get("left_growth_pct")),
                "right_entity_id": result.get("right_entity_id"),
                "right_entity_name": result.get("right_entity_name"),
                "right_growth_pct": _decimal_string(result.get("right_growth_pct")),
                "difference_percentage_points": _decimal_string(
                    result.get("difference_percentage_points")
                ),
            }
        return _canonical_value(result)

    def _normalize_labeled_comparison(
        self,
        task: TaskPackage,
        oracle_output: dict[str, Any],
        node_outputs: Mapping[str, dict[str, Any]],
    ) -> dict[str, Any]:
        projection = task.oracle.selection_contract.get("answer_projection")
        if not isinstance(projection, dict):
            return {"invalid_result": "missing_labeled_comparison_projection"}
        left_ref = str(projection.get("left_operation_ref") or "")
        right_ref = str(projection.get("right_operation_ref") or "")
        if not left_ref or not right_ref:
            return {"invalid_result": "incomplete_labeled_comparison_projection"}
        higher_ref = _normalized_operation_ref(oracle_output.get("higher_ref"))
        selected_prefix: str | None
        if higher_ref == _normalized_operation_ref(left_ref):
            selected_prefix = "left"
        elif higher_ref == _normalized_operation_ref(right_ref):
            selected_prefix = "right"
        elif higher_ref is None:
            selected_prefix = None
        else:
            return {"invalid_result": "unknown_labeled_comparison_winner"}
        result = {
            "selected_entity_id": (
                projection.get(f"{selected_prefix}_entity_id") if selected_prefix else None
            ),
            "selected_entity_name": (
                projection.get(f"{selected_prefix}_entity_name") if selected_prefix else None
            ),
            "left_entity_id": projection.get("left_entity_id"),
            "left_entity_name": projection.get("left_entity_name"),
            "left_growth_pct": _node_scalar(node_outputs, left_ref),
            "right_entity_id": projection.get("right_entity_id"),
            "right_entity_name": projection.get("right_entity_name"),
            "right_growth_pct": _node_scalar(node_outputs, right_ref),
            "difference_percentage_points": oracle_output.get("difference"),
        }
        return self._normalize(task.public.answer_schema, result)


def _decimal_string(value: Any) -> str | None:
    if value is None:
        return None
    try:
        normalized = Decimal(str(value)).normalize()
    except (InvalidOperation, TypeError, ValueError):
        return str(value)
    return format(normalized, "f")


def _normalized_operation_ref(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    for prefix in ("operation:", "op:"):
        if text.startswith(prefix):
            return text.removeprefix(prefix)
    return text


def _node_scalar(
    node_outputs: Mapping[str, dict[str, Any]],
    node_ref: str,
) -> Any:
    output = node_outputs.get(node_ref)
    if not isinstance(output, dict):
        output = node_outputs.get(_normalized_operation_ref(node_ref) or "")
    return output.get("value") if isinstance(output, dict) else None


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


def _allowed_payload_fields(answer_schema: dict[str, Any]) -> set[str]:
    return set(answer_schema.get("allowed_payload_fields") or ())
