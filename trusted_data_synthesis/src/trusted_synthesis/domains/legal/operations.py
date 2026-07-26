from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from trusted_synthesis.core.operations.registry import (
    OperationRegistry,
    default_registry,
    make_operation_definition,
)
from trusted_synthesis.core.operations.schema import OperationInput, OperationVerification


class LegalRuleApplicabilityExecutor:
    def execute(
        self, inputs: tuple[OperationInput, ...], parameters: dict[str, Any]
    ) -> dict[str, Any]:
        if len(inputs) != 1:
            raise ValueError("legal rule applicability requires one rule")
        rule = _mapping(inputs[0].value)
        conditions = set(str(item) for item in parameters.get("satisfied_conditions") or ())
        exceptions = set(str(item) for item in parameters.get("present_exceptions") or ())
        required = set(str(item) for item in rule.get("conditions") or ())
        registered_exceptions = set(str(item) for item in rule.get("exceptions") or ())
        missing = sorted(required - conditions)
        triggered = sorted(registered_exceptions & exceptions)
        return {
            "applicable": not missing and not triggered,
            "authority": rule.get("authority"),
            "legal_effect": rule.get("legal_effect"),
            "missing_conditions": missing,
            "triggered_exceptions": triggered,
        }


class LegalRuleApplicabilityVerifier:
    def verify(
        self,
        inputs: tuple[OperationInput, ...],
        parameters: dict[str, Any],
        observed_output: dict[str, Any],
    ) -> OperationVerification:
        if len(inputs) != 1:
            return _verification(None, observed_output, "legal_apply_rule_arity")
        rule = _mapping(inputs[0].value)
        conditions = {str(item) for item in parameters.get("satisfied_conditions") or ()}
        present = {str(item) for item in parameters.get("present_exceptions") or ()}
        missing = sorted({str(item) for item in rule.get("conditions") or ()} - conditions)
        triggered = sorted({str(item) for item in rule.get("exceptions") or ()} & present)
        expected = {
            "applicable": not missing and not triggered,
            "authority": rule.get("authority"),
            "legal_effect": rule.get("legal_effect"),
            "missing_conditions": missing,
            "triggered_exceptions": triggered,
        }
        return _verification(expected, observed_output, "legal_apply_rule_output")


class LegalAuthorityResolverExecutor:
    def execute(
        self, inputs: tuple[OperationInput, ...], parameters: dict[str, Any]
    ) -> dict[str, Any]:
        return _resolve_authority(inputs, parameters)


class LegalAuthorityResolverVerifier:
    def verify(
        self,
        inputs: tuple[OperationInput, ...],
        parameters: dict[str, Any],
        observed_output: dict[str, Any],
    ) -> OperationVerification:
        if not inputs:
            return _verification(None, observed_output, "legal_authority_non_empty")
        expected = _resolve_authority(inputs, parameters)
        return _verification(expected, observed_output, "legal_authority_output")


def legal_operation_registry() -> OperationRegistry:
    registry = default_registry()
    registry.register(
        make_operation_definition(
            "legal_apply_rule",
            LegalRuleApplicabilityExecutor(),
            LegalRuleApplicabilityVerifier(),
            "one:any",
            "structured",
            "none",
            ("conditions_complete", "exceptions_checked"),
        )
    )
    registry.register(
        make_operation_definition(
            "legal_resolve_authority",
            LegalAuthorityResolverExecutor(),
            LegalAuthorityResolverVerifier(),
            "many:any",
            "structured",
            "none",
            ("applicable_only", "authority_priority_registered"),
        )
    )
    return registry


def _resolve_authority(
    inputs: tuple[OperationInput, ...], parameters: dict[str, Any]
) -> dict[str, Any]:
    if not inputs:
        raise ValueError("legal authority resolution requires rule decisions")
    priority = {
        str(authority): index
        for index, authority in enumerate(parameters.get("authority_priority") or ())
    }
    eligible = [item for item in inputs if bool(_mapping(item.value).get("applicable"))]
    if not eligible:
        return {
            "applicable": False,
            "selected_ref": None,
            "authority": None,
            "legal_effect": None,
        }
    unknown = [
        str(_mapping(item.value).get("authority"))
        for item in eligible
        if str(_mapping(item.value).get("authority")) not in priority
    ]
    if unknown:
        raise ValueError(f"authority priority is incomplete: {sorted(unknown)}")
    selected = min(
        eligible,
        key=lambda item: (
            priority[str(_mapping(item.value).get("authority"))],
            item.ref_id,
        ),
    )
    value = _mapping(selected.value)
    return {
        "applicable": True,
        "selected_ref": selected.ref_id,
        "authority": value.get("authority"),
        "legal_effect": value.get("legal_effect"),
    }


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="python", exclude_none=True)
    if isinstance(value, dict):
        return value
    raise ValueError("legal operation input must be structured")


def _verification(
    expected: dict[str, Any] | None,
    observed: dict[str, Any],
    invariant: str,
) -> OperationVerification:
    passed = expected is not None and (not observed or observed == expected)
    return OperationVerification(
        passed=passed,
        expected_output=expected,
        invariant_failures=() if passed else (invariant,),
        message="Legal operation verified" if passed else "Legal operation mismatch",
    )
