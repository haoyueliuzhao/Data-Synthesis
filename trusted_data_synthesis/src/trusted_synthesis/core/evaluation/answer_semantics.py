from __future__ import annotations

import copy
import json
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

ANSWER_SEMANTICS_SCHEMA_VERSION = "prospective_answer_semantics.v1"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class AnswerSemanticSchema(FrozenModel):
    schema_id: str = Field(min_length=1)
    required_result_fields: tuple[str, ...] = Field(min_length=1)
    optional_result_fields: tuple[str, ...] = ()
    decimal_field_paths: tuple[tuple[str, ...], ...] = ()
    exact_result_field_set_required: bool = True
    floating_tolerance_allowed: bool = False
    alias_normalization_allowed: bool = False
    schema_version: str = ANSWER_SEMANTICS_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_schema(self) -> AnswerSemanticSchema:
        required = self.required_result_fields
        optional = self.optional_result_fields
        if (
            required != tuple(sorted(set(required)))
            or optional != tuple(sorted(set(optional)))
            or set(required) & set(optional)
            or any(
                not path or path[0] not in set(required) | set(optional)
                for path in self.decimal_field_paths
            )
            or self.decimal_field_paths != tuple(sorted(set(self.decimal_field_paths)))
            or self.floating_tolerance_allowed
            or self.alias_normalization_allowed
        ):
            raise ValueError("prospective Answer Semantic Schema changed")
        if self.schema_id != answer_semantic_schema_id(self):
            raise ValueError("prospective Answer Semantic Schema identity changed")
        return self


class AnswerSemanticComparison(FrozenModel):
    comparison_id: str = Field(min_length=1)
    schema_id: str = Field(min_length=1)
    answer_schema_match: bool
    answer_exact_json_match: bool
    answer_canonical_semantic_match: bool
    reference_identity_match: bool
    observed_canonical_result: dict[str, Any] | None = None
    expected_canonical_result: dict[str, Any]
    schema_failure_ids: tuple[str, ...]
    semantic_mismatch_paths: tuple[str, ...]
    decimal_comparison_exact: bool = True
    floating_tolerance_used: bool = False
    schema_version: str = "prospective_answer_semantic_comparison.v1"

    @model_validator(mode="after")
    def validate_comparison(self) -> AnswerSemanticComparison:
        if self.answer_canonical_semantic_match and (
            not self.answer_schema_match or self.semantic_mismatch_paths
        ):
            raise ValueError("semantic Answer match is inconsistent")
        if self.floating_tolerance_used:
            raise ValueError("prospective Answer comparison used floating tolerance")
        if self.comparison_id != answer_semantic_comparison_id(self):
            raise ValueError("prospective Answer comparison identity changed")
        return self


def answer_semantic_schema_id(value: AnswerSemanticSchema) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"schema_id"}),
        prefix="prospective_answer_semantic_schema:",
    )


def answer_semantic_comparison_id(value: AnswerSemanticComparison) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"comparison_id"}),
        prefix="prospective_answer_semantic_comparison:",
    )


def make_answer_semantic_schema(
    *,
    required_result_fields: Sequence[str],
    optional_result_fields: Sequence[str] = (),
    decimal_field_paths: Sequence[Sequence[str]] = (),
) -> AnswerSemanticSchema:
    values = {
        "required_result_fields": tuple(sorted(set(required_result_fields))),
        "optional_result_fields": tuple(sorted(set(optional_result_fields))),
        "decimal_field_paths": tuple(
            sorted(set(tuple(str(item) for item in path) for path in decimal_field_paths))
        ),
    }
    provisional = AnswerSemanticSchema.model_construct(schema_id="pending", **values)
    return AnswerSemanticSchema(schema_id=answer_semantic_schema_id(provisional), **values)


def canonicalize_decimal_field(value: Any) -> str:
    if isinstance(value, bool) or value is None:
        raise ValueError("Decimal answer field must be a finite number or numeric string")
    try:
        normalized = Decimal(str(value)).normalize()
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError("Decimal answer field is not numeric") from error
    if not normalized.is_finite():
        raise ValueError("Decimal answer field must be finite")
    if normalized == 0:
        normalized = Decimal(0)
    return format(normalized, "f")


def compare_answer_by_schema(
    observed: Mapping[str, Any] | None,
    expected: Mapping[str, Any],
    schema: AnswerSemanticSchema,
) -> AnswerSemanticComparison:
    failures: list[str] = []
    required = set(schema.required_result_fields)
    allowed = required | set(schema.optional_result_fields)
    if observed is None:
        failures.append("result_missing_or_not_object")
    else:
        missing = required - set(observed)
        extra = set(observed) - allowed
        if missing:
            failures.append(f"required_fields_missing:{','.join(sorted(missing))}")
        if schema.exact_result_field_set_required and extra:
            failures.append(f"unexpected_result_fields:{','.join(sorted(extra))}")
    expected_missing = required - set(expected)
    expected_extra = set(expected) - allowed
    if expected_missing or (schema.exact_result_field_set_required and expected_extra):
        raise ValueError("expected Answer does not satisfy its frozen Semantic Schema")

    observed_canonical = copy.deepcopy(dict(observed)) if observed is not None else None
    expected_canonical = copy.deepcopy(dict(expected))
    for path in schema.decimal_field_paths:
        try:
            expected_value = _value_at_path(expected_canonical, path)
            _set_value_at_path(
                expected_canonical,
                path,
                canonicalize_decimal_field(expected_value),
            )
        except ValueError as error:
            raise ValueError(f"expected Decimal field {'.'.join(path)} is invalid") from error
        if observed_canonical is None:
            continue
        try:
            observed_value = _value_at_path(observed_canonical, path)
            _set_value_at_path(
                observed_canonical,
                path,
                canonicalize_decimal_field(observed_value),
            )
        except ValueError:
            failures.append(f"decimal_field_invalid:{'.'.join(path)}")

    schema_match = not failures
    exact_match = bool(
        observed is not None and _canonical_json(observed) == _canonical_json(expected)
    )
    semantic_mismatches = (
        _mismatch_paths(observed_canonical, expected_canonical)
        if observed_canonical is not None
        else ("$",)
    )
    semantic_match = schema_match and not semantic_mismatches
    reference_match = bool(
        observed_canonical is not None
        and _mask_decimal_paths(observed_canonical, schema.decimal_field_paths)
        == _mask_decimal_paths(expected_canonical, schema.decimal_field_paths)
    )
    values = {
        "schema_id": schema.schema_id,
        "answer_schema_match": schema_match,
        "answer_exact_json_match": exact_match,
        "answer_canonical_semantic_match": semantic_match,
        "reference_identity_match": reference_match,
        "observed_canonical_result": observed_canonical,
        "expected_canonical_result": expected_canonical,
        "schema_failure_ids": tuple(sorted(set(failures))),
        "semantic_mismatch_paths": semantic_mismatches,
    }
    provisional = AnswerSemanticComparison.model_construct(comparison_id="pending", **values)
    return AnswerSemanticComparison(
        comparison_id=answer_semantic_comparison_id(provisional),
        **values,
    )


def _value_at_path(value: Mapping[str, Any], path: Sequence[str]) -> Any:
    current: Any = value
    for segment in path:
        if not isinstance(current, Mapping) or segment not in current:
            raise ValueError("Answer field path is absent")
        current = current[segment]
    return current


def _set_value_at_path(value: dict[str, Any], path: Sequence[str], replacement: Any) -> None:
    current = value
    for segment in path[:-1]:
        child = current.get(segment)
        if not isinstance(child, dict):
            raise ValueError("Answer field path is not an object path")
        current = child
    current[path[-1]] = replacement


def _mask_decimal_paths(
    value: Mapping[str, Any],
    paths: Sequence[Sequence[str]],
) -> dict[str, Any]:
    masked = copy.deepcopy(dict(value))
    for path in paths:
        try:
            _set_value_at_path(masked, path, "<decimal>")
        except ValueError:
            continue
    return masked


def _mismatch_paths(left: Any, right: Any, prefix: str = "$") -> tuple[str, ...]:
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        paths: list[str] = []
        for key in sorted(set(left) | set(right)):
            if key not in left or key not in right:
                paths.append(f"{prefix}.{key}")
            else:
                paths.extend(_mismatch_paths(left[key], right[key], f"{prefix}.{key}"))
        return tuple(paths)
    if isinstance(left, list) and isinstance(right, list):
        paths = []
        for index in range(max(len(left), len(right))):
            if index >= len(left) or index >= len(right):
                paths.append(f"{prefix}[{index}]")
            else:
                paths.extend(_mismatch_paths(left[index], right[index], f"{prefix}[{index}]"))
        return tuple(paths)
    return () if left == right else (prefix,)


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
