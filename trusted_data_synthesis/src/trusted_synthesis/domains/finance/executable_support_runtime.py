from __future__ import annotations

from typing import Any

from trusted_synthesis.core.evidence.payloads import ScalarObservation
from trusted_synthesis.domains.finance.agent_tools import finance_archive_agent_tool_specs
from trusted_synthesis.domains.finance.interactive_agent_runtime import (
    FinanceArchiveInteractiveToolRuntime,
    _provenance_hashes,
    _StoredOperation,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.tools import AgentToolResult, AgentToolSpec

FINANCE_EXECUTABLE_SUPPORT_RUNTIME_ID = "finance.executable_support_runtime"
FINANCE_EXECUTABLE_SUPPORT_RUNTIME_VERSION = "finance_executable_support_runtime.v1"
FINANCE_EXECUTABLE_SUPPORT_TOOLSET_VERSION = "finance_executable_support_toolset.v1"
FINANCE_EXECUTABLE_NORMALIZATION_POLICY_VERSION = "finance_executable_normalization_policy.v1"

_NORMALIZATION_FIELDS = (
    "predicate",
    "definition_id",
    "unit",
    "currency",
    "time_basis",
    "frequency",
)


def finance_executable_support_agent_tool_specs() -> tuple[AgentToolSpec, ...]:
    """Version-isolated toolset whose normalization output is a consumable operation."""

    values = []
    for item in finance_archive_agent_tool_specs():
        update: dict[str, Any] = {"tool_version": FINANCE_EXECUTABLE_SUPPORT_TOOLSET_VERSION}
        if item.tool_id == "normalize_metric_unit_period":
            update.update(
                {
                    "description": (
                        "Resolve selected Finance Evidence against one public target definition. "
                        "On success, copy normalized_operation_ref and each normalized value's "
                        "selector into downstream calculator operands; raw Evidence bypass is "
                        "not a normalized execution."
                    ),
                    "output_contract": {
                        "normalized_values": "array[typed normalized value with selector]",
                        "compatibility_report": "object",
                        "policy_hash": "string",
                        "normalized_operation_ref": "string",
                    },
                    "required_output_fields": (
                        "normalized_values",
                        "compatibility_report",
                        "policy_hash",
                        "normalized_operation_ref",
                    ),
                }
            )
        values.append(item.model_copy(update=update))
    return tuple(values)


class FinanceExecutableSupportRuntime(FinanceArchiveInteractiveToolRuntime):
    """Finance Runtime v1 with typed, downstream-consumable normalization lineage."""

    def _normalize(self, arguments: dict[str, Any]) -> AgentToolResult:
        evidence_ids_raw = arguments.get("evidence_ids")
        if not isinstance(evidence_ids_raw, list) or not evidence_ids_raw:
            raise ValueError("evidence_ids must be a nonempty array")
        evidence_ids = tuple(str(item) for item in evidence_ids_raw)
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("normalization Evidence IDs are duplicated")
        target = arguments.get("target_definition")
        if not isinstance(target, dict):
            raise ValueError("target_definition must be an object")
        missing_target = [field for field in _NORMALIZATION_FIELDS if field not in target]
        if missing_target:
            raise ValueError(f"target_definition is incomplete: {missing_target}")

        evidence = self._selected_evidence(evidence_ids)
        if any(not isinstance(item.payload, ScalarObservation) for item in evidence):
            raise ValueError("normalization requires scalar Evidence")

        def observed_value(item: Any, field: str) -> Any:
            values = {
                "predicate": item.predicate,
                "definition_id": item.definition.definition_id,
                "unit": item.payload.unit,
                "currency": item.payload.currency,
                "time_basis": item.temporal_context.basis,
                "frequency": item.temporal_context.frequency,
            }
            return values[field]

        mismatches = {
            field: [observed_value(item, field) for item in evidence]
            for field in _NORMALIZATION_FIELDS
            if any(observed_value(item, field) != target[field] for item in evidence)
        }
        selected = tuple(
            item
            for item in evidence
            if all(observed_value(item, field) == target[field] for field in _NORMALIZATION_FIELDS)
        )
        if len(selected) != 1:
            raise ValueError(
                "normalization target must identify exactly one selected Evidence item"
            )
        selected_item = selected[0]
        selector = "normalized_inputs.target"
        normalized_output = {
            "normalized_inputs": {
                "target": selected_item.payload.model_dump(mode="json", exclude_none=True)
            }
        }
        policy_hash = canonical_hash(
            {
                "version": FINANCE_EXECUTABLE_NORMALIZATION_POLICY_VERSION,
                "target": target,
                "evidence_ids": evidence_ids,
                "selected_evidence_id": selected_item.evidence_id,
            },
            prefix="finance_executable_normalization_policy:",
        )
        operation_hash = canonical_hash(
            {
                "operator_id": "normalize_metric_unit_period",
                "inputs": evidence_ids,
                "target": target,
                "output": normalized_output,
                "policy_hash": policy_hash,
            },
            prefix="finance_executable_normalization_operation:",
        )
        operation_ref = f"operation:{operation_hash}"
        self._operations[operation_ref] = _StoredOperation(
            operation_ref=operation_ref,
            operator_id="normalize_metric_unit_period",
            output=normalized_output,
            evidence_ids=(selected_item.evidence_id,),
        )
        return AgentToolResult(
            status="succeeded",
            result={
                "normalized_values": [
                    {
                        "evidence_id": selected_item.evidence_id,
                        "value": str(selected_item.payload.value),
                        "unit": selected_item.payload.unit,
                        "currency": selected_item.payload.currency,
                        "period": selected_item.temporal_context.label,
                        "selector": selector,
                    }
                ],
                "compatibility_report": {
                    "input_compatible": not mismatches,
                    "target_resolution_complete": True,
                    "mismatches": mismatches,
                },
                "policy_hash": policy_hash,
                "normalized_operation_ref": operation_ref,
            },
            evidence_ids=evidence_ids,
            provenance_hashes=_provenance_hashes(evidence),
        )
