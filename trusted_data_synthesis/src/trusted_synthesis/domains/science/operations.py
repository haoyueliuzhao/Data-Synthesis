from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from trusted_synthesis.core.operations.registry import (
    OperationRegistry,
    default_registry,
    make_operation_definition,
)
from trusted_synthesis.core.operations.schema import OperationInput, OperationVerification


class ProtocolAlignmentExecutor:
    def execute(
        self, inputs: tuple[OperationInput, ...], parameters: dict[str, Any]
    ) -> dict[str, Any]:
        return _align(inputs)


class ProtocolAlignmentVerifier:
    def verify(
        self,
        inputs: tuple[OperationInput, ...],
        parameters: dict[str, Any],
        observed_output: dict[str, Any],
    ) -> OperationVerification:
        expected = _align(inputs)
        return _verification(expected, observed_output, "science_protocol_alignment")


class EffectComparisonExecutor:
    def execute(
        self, inputs: tuple[OperationInput, ...], parameters: dict[str, Any]
    ) -> dict[str, Any]:
        return _compare_effect(inputs)


class EffectComparisonVerifier:
    def verify(
        self,
        inputs: tuple[OperationInput, ...],
        parameters: dict[str, Any],
        observed_output: dict[str, Any],
    ) -> OperationVerification:
        expected = _compare_effect(inputs)
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
        )
    )
    return registry


def _align(inputs: tuple[OperationInput, ...]) -> dict[str, Any]:
    if len(inputs) != 2:
        raise ValueError("protocol alignment requires two experimental results")
    left, right = (_mapping(item.value) for item in inputs)
    fields = ("metric", "unit", "dataset", "method", "protocol")
    mismatches = [field for field in fields if left.get(field) != right.get(field)]
    return {"comparable": not mismatches, "mismatches": mismatches}


def _compare_effect(inputs: tuple[OperationInput, ...]) -> dict[str, Any]:
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
    overlap = _intervals_overlap(left.get("uncertainty"), right.get("uncertainty"))
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


def _intervals_overlap(left: Any, right: Any) -> bool:
    if not isinstance(left, dict) or not isinstance(right, dict):
        raise ValueError("effect comparison requires uncertainty intervals")
    return Decimal(str(left["lower"])) <= Decimal(str(right["upper"])) and Decimal(
        str(right["lower"])
    ) <= Decimal(str(left["upper"]))


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="python", exclude_none=True)
    if isinstance(value, dict):
        return value
    raise ValueError("science operation input must be structured")


def _verification(
    expected: dict[str, Any], observed: dict[str, Any], invariant: str
) -> OperationVerification:
    passed = not observed or observed == expected
    return OperationVerification(
        passed=passed,
        expected_output=expected,
        invariant_failures=() if passed else (invariant,),
        message="Science operation verified" if passed else "Science operation mismatch",
    )
