from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

from trusted_synthesis.core.operations.registry import (
    OperationRegistry,
    default_registry,
    make_operation_definition,
)
from trusted_synthesis.core.operations.schema import OperationInput, OperationVerification


class ScienceProtocolAlignment(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    comparable: bool
    mismatches: list[str]


class ScienceEffectComparison(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    higher_ref: str | None
    difference: str
    uncertainty_intervals_overlap: bool
    qualified_conclusion: str


class ProtocolAlignmentExecutor:
    def execute(
        self, inputs: tuple[OperationInput, ...], parameters: dict[str, Any]
    ) -> dict[str, Any]:
        if len(inputs) != 2:
            raise ValueError("protocol alignment requires two experimental results")
        left, right = (_mapping(item.value) for item in inputs)
        fields = ("metric", "unit", "dataset", "method", "protocol")
        mismatches = [field for field in fields if left.get(field) != right.get(field)]
        return {"comparable": not mismatches, "mismatches": mismatches}


class ProtocolAlignmentVerifier:
    def verify(
        self,
        inputs: tuple[OperationInput, ...],
        parameters: dict[str, Any],
        observed_output: dict[str, Any],
    ) -> OperationVerification:
        if len(inputs) != 2:
            return _verification(None, observed_output, "science_protocol_alignment_arity")
        first = _mapping(inputs[0].value)
        second = _mapping(inputs[1].value)
        compared_fields = ("metric", "unit", "dataset", "method", "protocol")
        mismatches = [field for field in compared_fields if first.get(field) != second.get(field)]
        expected = {"comparable": len(mismatches) == 0, "mismatches": mismatches}
        return _verification(expected, observed_output, "science_protocol_alignment")


class EffectComparisonExecutor:
    def execute(
        self, inputs: tuple[OperationInput, ...], parameters: dict[str, Any]
    ) -> dict[str, Any]:
        if len(inputs) != 3:
            raise ValueError("effect comparison requires alignment and two results")
        alignment = _mapping(inputs[0].value)
        if not alignment.get("comparable"):
            raise ValueError("experimental protocols are not comparable")
        left = _mapping(inputs[1].value)
        right = _mapping(inputs[2].value)
        left_value = Decimal(str(left["value"]))
        right_value = Decimal(str(right["value"]))
        higher_ref = None
        if left_value > right_value:
            higher_ref = inputs[1].ref_id
        elif right_value > left_value:
            higher_ref = inputs[2].ref_id
        overlap = _executor_intervals_overlap(left.get("uncertainty"), right.get("uncertainty"))
        return {
            "higher_ref": higher_ref,
            "difference": str(abs(left_value - right_value)),
            "uncertainty_intervals_overlap": overlap,
            "qualified_conclusion": (
                "observed_difference_with_overlapping_uncertainty"
                if overlap
                else "observed_difference_with_separated_uncertainty"
            ),
        }


class EffectComparisonVerifier:
    def verify(
        self,
        inputs: tuple[OperationInput, ...],
        parameters: dict[str, Any],
        observed_output: dict[str, Any],
    ) -> OperationVerification:
        if len(inputs) != 3:
            return _verification(None, observed_output, "science_effect_comparison_arity")
        alignment = _mapping(inputs[0].value)
        if alignment.get("comparable") is not True:
            return _verification(None, observed_output, "science_protocol_comparable")
        first = _mapping(inputs[1].value)
        second = _mapping(inputs[2].value)
        first_value = Decimal(str(first["value"]))
        second_value = Decimal(str(second["value"]))
        higher_ref = (
            inputs[1].ref_id
            if first_value > second_value
            else inputs[2].ref_id
            if second_value > first_value
            else None
        )
        overlap = _oracle_intervals_overlap(first.get("uncertainty"), second.get("uncertainty"))
        expected = {
            "higher_ref": higher_ref,
            "difference": str(max(first_value, second_value) - min(first_value, second_value)),
            "uncertainty_intervals_overlap": overlap,
            "qualified_conclusion": (
                "observed_difference_with_overlapping_uncertainty"
                if overlap
                else "observed_difference_with_separated_uncertainty"
            ),
        }
        return _verification(expected, observed_output, "science_effect_comparison")


def science_operation_registry() -> OperationRegistry:
    registry = default_registry()
    registry.register(
        make_operation_definition(
            "science_align_protocol",
            ProtocolAlignmentExecutor(),
            ProtocolAlignmentVerifier(),
            "two:any",
            "structured",
            "none",
            ("metric_aligned", "protocol_aligned", "dataset_aligned"),
            output_model=ScienceProtocolAlignment,
            tool_capability="protocol_analyzer",
            implementation_dependencies=(_mapping,),
        )
    )
    registry.register(
        make_operation_definition(
            "science_compare_effect",
            EffectComparisonExecutor(),
            EffectComparisonVerifier(),
            "many:any",
            "structured",
            "none",
            ("protocol_comparable", "uncertainty_preserved"),
            output_model=ScienceEffectComparison,
            tool_capability="protocol_analyzer",
            implementation_dependencies=(
                _mapping,
                _executor_intervals_overlap,
                _oracle_intervals_overlap,
            ),
        )
    )
    return registry


def _executor_intervals_overlap(left: Any, right: Any) -> bool:
    if not isinstance(left, dict) or not isinstance(right, dict):
        raise ValueError("effect comparison requires uncertainty intervals")
    return Decimal(str(left["lower"])) <= Decimal(str(right["upper"])) and Decimal(
        str(right["lower"])
    ) <= Decimal(str(left["upper"]))


def _oracle_intervals_overlap(first: Any, second: Any) -> bool:
    if not isinstance(first, dict) or not isinstance(second, dict):
        raise ValueError("oracle comparison requires uncertainty intervals")
    first_lower = Decimal(str(first["lower"]))
    first_upper = Decimal(str(first["upper"]))
    second_lower = Decimal(str(second["lower"]))
    second_upper = Decimal(str(second["upper"]))
    return max(first_lower, second_lower) <= min(first_upper, second_upper)


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="python", exclude_none=True)
    if isinstance(value, dict):
        return value
    raise ValueError("science operation input must be structured")


def _verification(
    expected: dict[str, Any] | None, observed: dict[str, Any], invariant: str
) -> OperationVerification:
    passed = expected is not None and observed == expected
    return OperationVerification(
        passed=passed,
        expected_output=expected,
        invariant_failures=() if passed else (invariant,),
        message="Science operation verified" if passed else "Science operation mismatch",
    )
