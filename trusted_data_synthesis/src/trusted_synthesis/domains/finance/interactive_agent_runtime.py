from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.payloads import ScalarObservation
from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.core.operations.registry import OperationRegistry, default_registry
from trusted_synthesis.core.operations.schema import OperationInput
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.tools import (
    ARGUMENT_PATCH_REQUIRED_POLICY,
    AgentToolCall,
    AgentToolEnvironmentManifest,
    AgentToolResult,
)

FINANCE_ARCHIVE_INTERACTIVE_RUNTIME_VERSION = "finance_archive_interactive_runtime.v9"
FINANCE_TYPED_RECOVERY_SCENARIO_VERSION = "finance_typed_recovery_scenario.v1"
FINANCE_CAPABILITY_MECHANISM_SCENARIO_VERSION = "finance_capability_mechanism_scenario.v3"
FINANCE_CAPABILITY_MECHANISM_ORACLE_KEY = "v25_22_capability_mechanism_scenario"

_PUBLIC_SUBJECT_ID_SUFFIXES = ("_US", "_COUNTRY", "_HK", "_CN")
FINANCE_ARCHIVE_NORMALIZATION_POLICY_VERSION = "finance_archive_normalization_policy.v1"
_MAX_QUERY_RESULTS = 12
_TOKEN_PATTERN = re.compile(r"[0-9a-z]+|[\u4e00-\u9fff]", re.IGNORECASE)


@dataclass(frozen=True)
class _StoredOperation:
    operation_ref: str
    operator_id: str
    output: dict[str, Any]
    evidence_ids: tuple[str, ...]


class FinanceTypedRecoveryScenario(BaseModel):
    """Frozen, public-safe intervention used to observe an actual recovery transition."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scenario_id: str = Field(min_length=1)
    scope_identity: str = Field(min_length=1)
    trigger_tool: str = "query_structured_fact"
    forced_failure_count: int = Field(default=1, ge=1, le=1)
    error_code: str = "typed_selector_requires_refinement"
    mismatch_fields: tuple[str, ...] = Field(min_length=1)
    correction_policy: str = (
        "change at least one public selector after inspecting the failed observation"
    )
    schema_version: str = FINANCE_TYPED_RECOVERY_SCENARIO_VERSION

    @model_validator(mode="after")
    def validate_scenario(self) -> FinanceTypedRecoveryScenario:
        if self.trigger_tool != "query_structured_fact":
            raise ValueError("Finance recovery scenario must target structured selection")
        if self.scenario_id != finance_typed_recovery_scenario_id(self):
            raise ValueError("Finance typed recovery scenario identity is invalid")
        return self


def make_finance_typed_recovery_scenario(
    *, scope_identity: str, mismatch_fields: tuple[str, ...]
) -> FinanceTypedRecoveryScenario:
    values = {
        "scope_identity": scope_identity,
        "trigger_tool": "query_structured_fact",
        "forced_failure_count": 1,
        "error_code": "typed_selector_requires_refinement",
        "mismatch_fields": tuple(sorted(set(mismatch_fields))),
        "correction_policy": (
            "change at least one public selector after inspecting the failed observation"
        ),
        "schema_version": FINANCE_TYPED_RECOVERY_SCENARIO_VERSION,
    }
    provisional = FinanceTypedRecoveryScenario.model_construct(
        scenario_id="pending",
        **values,
    )
    return FinanceTypedRecoveryScenario(
        scenario_id=finance_typed_recovery_scenario_id(provisional),
        **values,
    )


def finance_typed_recovery_scenario_id(
    value: FinanceTypedRecoveryScenario,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"scenario_id"}),
        prefix="finance_typed_recovery_scenario:",
    )


class FinanceCompletionRole(BaseModel):
    """Public selector defining one independently observable completeness role."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    role_id: str = Field(min_length=1)
    subject_alias: str = Field(min_length=1)
    metric_alias: str = Field(min_length=1)
    period_label: str = Field(min_length=1)
    public_filters: dict[str, str] = Field(default_factory=dict)


class FinanceCapabilityMechanismScenario(BaseModel):
    """Public-safe Runtime intervention for capability-mechanism identification."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scenario_id: str = Field(min_length=1)
    mechanism_kind: Literal[
        "candidate_verification_and_repair",
        "state_dependent_control_and_stopping",
    ]
    candidate_payload: dict[str, Any] | None = None
    canonical_candidate_payload: dict[str, Any] | None = None
    repair_target_field: str | None = None
    preserve_fields: tuple[str, ...] = ()
    required_roles: tuple[FinanceCompletionRole, ...] = ()
    redundant_action_policy: Literal[
        "not_applicable",
        "reject_every_tool_call_after_verified_completion",
    ]
    transition_policy: Literal[
        "not_applicable",
        "require_incomplete_probe_before_remaining_roles",
    ]
    schema_version: str = FINANCE_CAPABILITY_MECHANISM_SCENARIO_VERSION

    @model_validator(mode="after")
    def validate_scenario(self) -> FinanceCapabilityMechanismScenario:
        if self.mechanism_kind == "candidate_verification_and_repair":
            if (
                not self.candidate_payload
                or not self.canonical_candidate_payload
                or not self.repair_target_field
            ):
                raise ValueError("candidate verification scenario lacks a localized candidate")
            if set(self.candidate_payload) != set(self.canonical_candidate_payload):
                raise ValueError("candidate verification canonical fields differ")
            if self.repair_target_field not in self.candidate_payload:
                raise ValueError("candidate verification target field is absent")
            mismatches = {
                field
                for field in self.candidate_payload
                if self.candidate_payload[field] != self.canonical_candidate_payload[field]
            }
            if mismatches != {self.repair_target_field}:
                raise ValueError("candidate verification must contain exactly one local error")
            if set(self.preserve_fields) != set(self.candidate_payload) - {
                self.repair_target_field
            }:
                raise ValueError("candidate verification preserve fields are incomplete")
            if (
                self.required_roles
                or self.redundant_action_policy != "not_applicable"
                or self.transition_policy != "not_applicable"
            ):
                raise ValueError("candidate verification scenario mixes stopping state")
        else:
            if (
                self.candidate_payload is not None
                or self.canonical_candidate_payload is not None
                or self.repair_target_field is not None
            ):
                raise ValueError("stopping scenario exposes candidate state")
            if self.preserve_fields:
                raise ValueError("stopping scenario exposes candidate preserve fields")
            if len(self.required_roles) < 2:
                raise ValueError("stopping scenario requires at least two observable roles")
            if len({item.role_id for item in self.required_roles}) != len(self.required_roles):
                raise ValueError("stopping scenario duplicates a public role")
            if (
                self.redundant_action_policy
                != "reject_every_tool_call_after_verified_completion"
            ):
                raise ValueError("stopping scenario lacks an asymmetric action cost")
            if (
                self.transition_policy
                != "require_incomplete_probe_before_remaining_roles"
            ):
                raise ValueError("stopping scenario lacks an observable state transition")
        if self.scenario_id != finance_capability_mechanism_scenario_id(self):
            raise ValueError("Finance capability mechanism scenario identity is invalid")
        return self


def make_candidate_verification_scenario(
    *,
    candidate_payload: Mapping[str, Any],
    canonical_candidate_payload: Mapping[str, Any],
    repair_target_field: str,
) -> FinanceCapabilityMechanismScenario:
    values = {
        "mechanism_kind": "candidate_verification_and_repair",
        "candidate_payload": dict(candidate_payload),
        "canonical_candidate_payload": dict(canonical_candidate_payload),
        "repair_target_field": repair_target_field,
        "preserve_fields": tuple(sorted(set(candidate_payload) - {repair_target_field})),
        "required_roles": (),
        "redundant_action_policy": "not_applicable",
        "transition_policy": "not_applicable",
    }
    provisional = FinanceCapabilityMechanismScenario.model_construct(
        scenario_id="pending", **values
    )
    return FinanceCapabilityMechanismScenario(
        scenario_id=finance_capability_mechanism_scenario_id(provisional), **values
    )


def make_state_dependent_stopping_scenario(
    *, required_roles: tuple[FinanceCompletionRole, ...]
) -> FinanceCapabilityMechanismScenario:
    values = {
        "mechanism_kind": "state_dependent_control_and_stopping",
        "candidate_payload": None,
        "canonical_candidate_payload": None,
        "repair_target_field": None,
        "preserve_fields": (),
        "required_roles": required_roles,
        "redundant_action_policy": "reject_every_tool_call_after_verified_completion",
        "transition_policy": "require_incomplete_probe_before_remaining_roles",
    }
    provisional = FinanceCapabilityMechanismScenario.model_construct(
        scenario_id="pending", **values
    )
    return FinanceCapabilityMechanismScenario(
        scenario_id=finance_capability_mechanism_scenario_id(provisional), **values
    )


def finance_capability_mechanism_scenario_id(
    value: FinanceCapabilityMechanismScenario,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"scenario_id"}),
        prefix="finance_capability_mechanism_scenario:",
    )


def capability_mechanism_scenario_from_oracle(
    selection_contract: Mapping[str, Any],
) -> FinanceCapabilityMechanismScenario | None:
    raw = selection_contract.get(FINANCE_CAPABILITY_MECHANISM_ORACLE_KEY)
    if raw is None:
        return None
    return FinanceCapabilityMechanismScenario.model_validate(raw)


def recovery_scenario_from_metadata(
    metadata: dict[str, Any],
) -> FinanceTypedRecoveryScenario | None:
    raw = metadata.get("typed_recovery_scenario")
    if raw is None:
        return None
    return FinanceTypedRecoveryScenario.model_validate(raw)


def finance_runtime_snapshot_hash(
    corpus_hash: str,
    scenario: FinanceTypedRecoveryScenario | None,
    capability_scenario: FinanceCapabilityMechanismScenario | None = None,
) -> str:
    if scenario is None and capability_scenario is None:
        return corpus_hash
    return canonical_hash(
        {
            "corpus_hash": corpus_hash,
            "typed_recovery_scenario": scenario,
            "capability_mechanism_scenario": capability_scenario,
        },
        prefix="finance_archive_runtime_snapshot:",
    )


class FinanceArchiveInteractiveToolRuntime:
    """Snapshot-bound Finance tools with per-rollout discovery and lineage state."""

    def __init__(
        self,
        corpus: EvidenceCorpus,
        manifest: AgentToolEnvironmentManifest,
        *,
        registry: OperationRegistry | None = None,
        recovery_scenario: FinanceTypedRecoveryScenario | None = None,
        capability_scenario: FinanceCapabilityMechanismScenario | None = None,
    ) -> None:
        if manifest.corpus_id != corpus.corpus_id or manifest.corpus_hash != corpus.corpus_hash:
            raise ValueError("Finance Agent runtime corpus differs from its frozen manifest")
        if manifest.network_policy != "forbidden":
            raise ValueError("Finance Archive Pilot requires an offline frozen environment")
        if manifest.snapshot_hash != finance_runtime_snapshot_hash(
            corpus.corpus_hash,
            recovery_scenario,
            capability_scenario,
        ):
            raise ValueError("Finance Agent runtime behavior differs from its frozen snapshot")
        self._corpus = corpus
        self._manifest = manifest
        self._registry = registry or default_registry()
        self._by_id = corpus.by_id()
        locator_groups: dict[str, list[str]] = {}
        for item in corpus.evidence:
            locator_groups.setdefault(_public_locator(item), []).append(item.evidence_id)
        self._locator_to_ids = {
            locator: tuple(sorted(evidence_ids)) for locator, evidence_ids in locator_groups.items()
        }
        self._discovered_ids: set[str] = set()
        self._selected_ids: set[str] = set()
        self._exposed_locators: set[str] = set()
        self._operations: dict[str, _StoredOperation] = {}
        self._recovery_scenario = recovery_scenario
        self._capability_scenario = capability_scenario
        self._verified_completion_reached = False
        self._incomplete_completion_probe_observed = False
        self._forced_recovery_failures = 0
        self._forced_recovery_selector_hash: str | None = None

    @property
    def manifest(self) -> AgentToolEnvironmentManifest:
        return self._manifest

    @property
    def discovered_evidence_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._discovered_ids))

    @property
    def selected_evidence_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._selected_ids))

    @property
    def operation_refs(self) -> tuple[str, ...]:
        return tuple(sorted(self._operations))

    def execute(self, call: AgentToolCall) -> AgentToolResult:
        if self._verified_completion_reached:
            return _failed(
                "redundant_action_after_verified_completion",
                "The public completeness contract was already verified. Every additional tool "
                "call incurs the frozen terminal redundancy cost; emit the final answer instead.",
                result={
                    "completion_state": {
                        "complete": True,
                        "redundant_action_cost_applied": True,
                    }
                },
            )
        transition_rejection = self._stopping_transition_rejection(call)
        if transition_rejection is not None:
            return transition_rejection
        handlers = {
            "search_archive": self._search_archive,
            "open_document": self._open_document,
            "query_structured_fact": self._query_structured_fact,
            "calculator": self._calculator,
            "normalize_metric_unit_period": self._normalize,
            "cross_check_evidence": self._cross_check,
        }
        handler = handlers.get(call.tool_id)
        if handler is None:
            return _failed("unknown_tool", f"unsupported Finance Archive tool: {call.tool_id}")
        try:
            return handler(call.arguments)
        except (InvalidOperation, TypeError, ValueError) as exc:
            return _failed(f"{call.tool_id}_contract", str(exc) or type(exc).__name__)

    def _stopping_transition_rejection(
        self,
        call: AgentToolCall,
    ) -> AgentToolResult | None:
        scenario = self._capability_scenario
        if (
            scenario is None
            or scenario.mechanism_kind != "state_dependent_control_and_stopping"
            or scenario.transition_policy
            != "require_incomplete_probe_before_remaining_roles"
            or self._incomplete_completion_probe_observed
            or call.tool_id == "cross_check_evidence"
        ):
            return None
        completion_state, _ = self._completion_state(scenario)
        resolved = completion_state["resolved_role_ids"]
        missing = completion_state["missing_role_ids"]
        if not resolved or not missing:
            return None
        return _failed(
            "incomplete_completion_probe_required",
            "The Host has observed a strict nonempty subset of required roles. Cross-check that "
            "subset now to observe completion_state.complete=false before any remaining role is "
            "made available.",
            result={"completion_state": completion_state},
        )

    def _search_archive(self, arguments: dict[str, Any]) -> AgentToolResult:
        query = _required_string(arguments, "query")
        limit = _required_int(arguments, "limit", minimum=1, maximum=_MAX_QUERY_RESULTS)
        subject_aliases = _string_tuple(arguments.get("subject_aliases", ()))
        period_labels = _string_tuple(arguments.get("period_labels", ()))
        source_filters = _string_tuple(arguments.get("source_filters", ()))
        query_tokens = _tokens(" ".join((query, *subject_aliases, *period_labels)))
        if not query_tokens:
            raise ValueError("Archive search query contains no searchable terms")
        ranked: list[tuple[int, str, EvidenceItem]] = []
        for item in self._corpus.evidence:
            if source_filters and not _matches_source(item, source_filters):
                continue
            if period_labels and not _matches_text(
                item.temporal_context.label or "", period_labels
            ):
                continue
            text = _search_text(item)
            score = len(query_tokens & _tokens(text))
            normalized_query = _normalize_text(query)
            if normalized_query and normalized_query in _normalize_text(text):
                score += 4
            if subject_aliases and _matches_text(
                " ".join((item.subject.subject_id, item.subject.name)),
                subject_aliases,
            ):
                score += 3
            if score:
                ranked.append((score, item.evidence_id, item))
        selected = tuple(
            item
            for _, _, item in sorted(
                ranked,
                key=lambda row: (-row[0], row[1]),
            )[:limit]
        )
        evidence_ids = tuple(item.evidence_id for item in selected)
        self._discovered_ids.update(evidence_ids)
        locators = tuple(_public_locator(item) for item in selected)
        self._exposed_locators.update(locators)
        query_hash = canonical_hash(
            {
                "query": query,
                "subject_aliases": subject_aliases,
                "period_labels": period_labels,
                "source_filters": source_filters,
                "limit": limit,
                "snapshot_hash": self._manifest.snapshot_hash,
            },
            prefix="finance_archive_search:",
        )
        return AgentToolResult(
            status="succeeded",
            result={
                "matches": [
                    _evidence_summary(item, public_locator=locator)
                    for item, locator in zip(selected, locators, strict=True)
                ],
                "query_hash": query_hash,
                "snapshot_hash": self._manifest.snapshot_hash,
            },
            evidence_ids=evidence_ids,
            provenance_hashes=_provenance_hashes(selected),
        )

    def _open_document(self, arguments: dict[str, Any]) -> AgentToolResult:
        locator = _required_string(arguments, "public_locator")
        if locator not in self._exposed_locators:
            return _failed(
                "locator_not_discovered",
                "open_document accepts only locators returned by search_archive",
            )
        evidence_ids = self._locator_to_ids.get(locator, ())
        selected = tuple(self._by_id[item] for item in evidence_ids)
        if not selected:
            return _failed("locator_not_found", "Archive locator has no frozen Evidence")
        self._selected_ids.update(evidence_ids)
        return AgentToolResult(
            status="succeeded",
            result={
                "content": {
                    "public_locator": locator,
                    "section_or_page": arguments.get("section_or_page"),
                    "facts": [_public_fact(item) for item in selected],
                },
                "evidence_ids": list(evidence_ids),
                "source_locator_hash": selected[0].source_locator.locator_hash,
            },
            evidence_ids=evidence_ids,
            provenance_hashes=_provenance_hashes(selected),
        )

    def _query_structured_fact(self, arguments: dict[str, Any]) -> AgentToolResult:
        subject_alias = _required_string(arguments, "subject_alias")
        metric_alias = _required_string(arguments, "metric_alias")
        period_label = _required_string(arguments, "period_label")
        filters = arguments.get("public_filters")
        if not isinstance(filters, dict):
            raise ValueError("public_filters must be an object")
        matches = tuple(
            item
            for item in self._corpus.evidence
            if _matches_subject(item, subject_alias)
            and _matches_metric(item, metric_alias)
            and _matches_exact(item.temporal_context.label or "", period_label)
            and _matches_public_filters(item, filters)
        )
        scenario = self._recovery_scenario
        selector_hash = canonical_hash(
            {
                "subject_alias": subject_alias,
                "metric_alias": metric_alias,
                "period_label": period_label,
                "public_filters": filters,
            },
            prefix="finance_typed_recovery_selector:",
        )
        if (
            scenario is not None
            and self._forced_recovery_failures < scenario.forced_failure_count
            and matches
        ):
            self._forced_recovery_failures += 1
            self._forced_recovery_selector_hash = selector_hash
            retry_contract = _typed_recovery_retry_contract(matches, filters)
            return _failed(
                scenario.error_code,
                "The typed selector reached a registered near-match branch. Inspect the "
                "public search observations, change at least one subject, metric, period, or "
                "public_filter selector, and retry the structured query. Registered mismatch "
                f"fields: {', '.join(scenario.mismatch_fields)}. Apply the public "
                "suggested_argument_patch in retry_contract when it is available.",
                result={"retry_contract": retry_contract},
            )
        if scenario is not None and self._forced_recovery_selector_hash == selector_hash:
            retry_contract = _typed_recovery_retry_contract(matches, filters)
            return _failed(
                "typed_selector_not_revised",
                "The retry repeated the failed typed selector. Change at least one public "
                "subject, metric, period, or filter selector before retrying; apply the "
                "suggested_argument_patch.",
                result={
                    "retry_contract": {
                        **retry_contract,
                        "policy": "selector_revision_required",
                        "maximum_identical_replays": 0,
                    }
                },
            )
        if len(matches) > _MAX_QUERY_RESULTS:
            return _failed(
                "structured_query_too_broad",
                f"structured query returned {len(matches)} facts; refine public filters",
            )
        if not matches:
            hints = tuple(
                {
                    "subject_alias": item.subject.subject_id,
                    "metric_alias": item.predicate,
                    "period_label": item.temporal_context.label,
                }
                for evidence_id in sorted(self._discovered_ids)
                if (item := self._by_id[evidence_id])
            )[:6]
            return _failed(
                "structured_query_no_match",
                "No exact fact matched. Use the subject, metric, and period labels exactly "
                "as returned by search_archive. Public selector hints from prior search: "
                + json.dumps(hints, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            )
        evidence_ids = tuple(item.evidence_id for item in matches)
        self._discovered_ids.update(evidence_ids)
        self._selected_ids.update(evidence_ids)
        query_hash = canonical_hash(
            {
                "subject_alias": subject_alias,
                "metric_alias": metric_alias,
                "period_label": period_label,
                "public_filters": filters,
                "snapshot_hash": self._manifest.snapshot_hash,
            },
            prefix="finance_structured_fact_query:",
        )
        return AgentToolResult(
            status="succeeded",
            result={
                "facts": [_public_fact(item) for item in matches],
                "evidence_ids": list(evidence_ids),
                "query_hash": query_hash,
            },
            evidence_ids=evidence_ids,
            provenance_hashes=_provenance_hashes(matches),
        )

    def _calculator(self, arguments: dict[str, Any]) -> AgentToolResult:
        operator_id = _required_string(arguments, "operator")
        operands = arguments.get("operands")
        parameters = arguments.get("parameters")
        if not isinstance(operands, list) or not operands:
            raise ValueError("calculator operands must be a nonempty array")
        if not isinstance(parameters, dict):
            raise ValueError("calculator parameters must be an object")
        definition = self._registry.require(operator_id)
        inputs: list[OperationInput] = []
        lineage: list[str] = []
        for index, operand in enumerate(operands):
            resolved, evidence_ids = self._resolve_operand(operand, index)
            inputs.append(resolved)
            lineage.extend(evidence_ids)
        evidence_ids = tuple(dict.fromkeys(lineage))
        if not evidence_ids:
            raise ValueError("calculator operands must retain selected Evidence lineage")
        evidence = tuple(self._by_id[item] for item in evidence_ids)
        resolved_inputs = tuple(inputs)
        self._registry.validate_inputs(definition, resolved_inputs)
        self._registry.validate_compatibility(definition, evidence, parameters)
        output = definition.executor.execute(resolved_inputs, parameters)
        self._registry.validate_output(definition, output)
        operation_hash = canonical_hash(
            {
                "operator_id": operator_id,
                "inputs": [
                    {"ref_id": item.ref_id, "value": item.value} for item in resolved_inputs
                ],
                "parameters": parameters,
                "output": output,
                "evidence_ids": evidence_ids,
                "registry_manifest": self._registry.manifest(),
            },
            prefix="finance_agent_operation:",
        )
        operation_ref = f"operation:{operation_hash}"
        self._operations[operation_ref] = _StoredOperation(
            operation_ref=operation_ref,
            operator_id=operator_id,
            output=output,
            evidence_ids=evidence_ids,
        )
        return AgentToolResult(
            status="succeeded",
            result={
                "result": {
                    "operator": operator_id,
                    "output": output,
                    "operation_ref": operation_ref,
                },
                "operation_hash": operation_hash,
            },
            evidence_ids=evidence_ids,
            provenance_hashes=_provenance_hashes(evidence),
        )

    def _resolve_operand(
        self,
        operand: Any,
        index: int,
    ) -> tuple[OperationInput, tuple[str, ...]]:
        if isinstance(operand, dict):
            evidence_id = operand.get("evidence_id")
            operation_ref = operand.get("operation_ref")
            if evidence_id is not None:
                return self._evidence_operand(str(evidence_id))
            if operation_ref is not None:
                return self._operation_operand(str(operation_ref), operand.get("selector"))
            if "value" in operand:
                ref_id = str(operand.get("ref_id") or f"literal:{index}")
                return OperationInput(ref_id=ref_id, value=operand["value"]), ()
            raise ValueError("calculator operand object needs evidence_id, operation_ref, or value")
        if isinstance(operand, str) and operand.startswith("evidence:"):
            return self._evidence_operand(operand)
        if isinstance(operand, str) and operand.startswith("operation:"):
            return self._operation_operand(operand, None)
        return OperationInput(ref_id=f"literal:{index}", value=operand), ()

    def _evidence_operand(
        self,
        evidence_id: str,
    ) -> tuple[OperationInput, tuple[str, ...]]:
        if evidence_id not in self._selected_ids:
            raise ValueError(f"calculator Evidence was not selected: {evidence_id}")
        item = self._by_id.get(evidence_id)
        if item is None:
            raise ValueError(f"calculator Evidence is unknown: {evidence_id}")
        return OperationInput(ref_id=evidence_id, value=item.payload), (evidence_id,)

    def _operation_operand(
        self,
        operation_ref: str,
        selector: Any,
    ) -> tuple[OperationInput, tuple[str, ...]]:
        stored = self._operations.get(operation_ref)
        if stored is None:
            raise ValueError(f"calculator operation reference is unknown: {operation_ref}")
        value: Any = stored.output
        if selector is not None:
            value = _select_mapping_value(stored.output, str(selector))
        return OperationInput(ref_id=operation_ref, value=value), stored.evidence_ids

    def _normalize(self, arguments: dict[str, Any]) -> AgentToolResult:
        evidence_ids = _evidence_id_tuple(arguments.get("evidence_ids"))
        target = arguments.get("target_definition")
        if not isinstance(target, dict):
            raise ValueError("target_definition must be an object")
        evidence = self._selected_evidence(evidence_ids)
        fields = {
            "predicate": lambda item: item.predicate,
            "definition_id": lambda item: item.definition.definition_id,
            "unit": lambda item: getattr(item.payload, "unit", None),
            "currency": lambda item: getattr(item.payload, "currency", None),
            "time_basis": lambda item: item.temporal_context.basis,
            "frequency": lambda item: item.temporal_context.frequency,
        }
        mismatches: dict[str, list[Any]] = {}
        for field, getter in fields.items():
            values = [getter(item) for item in evidence]
            expected = target.get(field)
            if expected is not None:
                if any(value != expected for value in values):
                    mismatches[field] = values
            elif (
                not values or any(value in (None, "") for value in values) or len(set(values)) != 1
            ):
                mismatches[field] = values
        policy_hash = canonical_hash(
            {
                "version": FINANCE_ARCHIVE_NORMALIZATION_POLICY_VERSION,
                "target": target,
                "evidence_ids": evidence_ids,
            },
            prefix="finance_agent_normalization_policy:",
        )
        return AgentToolResult(
            status="succeeded",
            result={
                "normalized_values": [
                    {
                        "evidence_id": item.evidence_id,
                        "value": _scalar_value(item),
                        "unit": getattr(item.payload, "unit", None),
                        "currency": getattr(item.payload, "currency", None),
                        "period": item.temporal_context.label,
                    }
                    for item in evidence
                ],
                "compatibility_report": {
                    "compatible": not mismatches,
                    "mismatches": mismatches,
                },
                "policy_hash": policy_hash,
            },
            evidence_ids=evidence_ids,
            provenance_hashes=_provenance_hashes(evidence),
        )

    def _cross_check(self, arguments: dict[str, Any]) -> AgentToolResult:
        evidence_ids = _evidence_id_tuple(arguments.get("evidence_ids"))
        claim_or_result = arguments.get("claim_or_result")
        if not isinstance(claim_or_result, dict):
            raise ValueError("claim_or_result must be an object")
        evidence = self._selected_evidence(evidence_ids)
        operation_refs = tuple(sorted(_find_operation_refs(claim_or_result)))
        unknown_operations = tuple(ref for ref in operation_refs if ref not in self._operations)
        conflicts: list[dict[str, Any]] = []
        if unknown_operations:
            conflicts.append(
                {
                    "type": "unknown_operation_reference",
                    "operation_refs": list(unknown_operations),
                }
            )
        missing_provenance = [
            item.evidence_id for item in evidence if not _provenance_complete(item)
        ]
        if missing_provenance:
            conflicts.append(
                {
                    "type": "missing_provenance",
                    "evidence_ids": missing_provenance,
                }
            )
        if not operation_refs and not self._operations:
            conflicts.append({"type": "no_replayable_calculation"})
        mechanism_report: dict[str, Any] = {}
        scenario = self._capability_scenario
        if scenario is not None and scenario.mechanism_kind == "candidate_verification_and_repair":
            candidate_report, candidate_conflicts = self._candidate_verification_report(
                scenario,
                claim_or_result,
                evidence,
            )
            mechanism_report["candidate_repair"] = candidate_report
            conflicts.extend(candidate_conflicts)
        if (
            scenario is not None
            and scenario.mechanism_kind == "state_dependent_control_and_stopping"
        ):
            completion_state, completion_conflicts = self._completion_state(scenario)
            mechanism_report["completion_state"] = completion_state
            if not completion_state["complete"]:
                self._incomplete_completion_probe_observed = True
            conflicts.extend(completion_conflicts)
        verification_hash = canonical_hash(
            {
                "evidence_ids": evidence_ids,
                "claim_or_result": claim_or_result,
                "known_operations": tuple(sorted(self._operations)),
                "mechanism_report": mechanism_report,
                "conflicts": conflicts,
                "snapshot_hash": self._manifest.snapshot_hash,
            },
            prefix="finance_agent_cross_check:",
        )
        verified = not conflicts
        if (
            verified
            and scenario is not None
            and scenario.mechanism_kind == "state_dependent_control_and_stopping"
        ):
            self._verified_completion_reached = True
        return AgentToolResult(
            status="succeeded",
            result={
                "verified": verified,
                "support": list(evidence_ids),
                "conflicts": conflicts,
                "verification_hash": verification_hash,
                **mechanism_report,
            },
            evidence_ids=evidence_ids,
            provenance_hashes=_provenance_hashes(evidence),
        )

    def _candidate_verification_report(
        self,
        scenario: FinanceCapabilityMechanismScenario,
        claim_or_result: Mapping[str, Any],
        evidence: tuple[EvidenceItem, ...],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        latest = next(reversed(self._operations.values()), None)
        target = str(scenario.repair_target_field)
        original = dict(scenario.candidate_payload or {})
        canonical = dict(scenario.canonical_candidate_payload or {})
        if latest is None:
            return (
                {
                    "localized": False,
                    "repair_verified": False,
                    "target_field": target,
                },
                [{"type": "candidate_replay_missing"}],
            )
        submitted_raw = claim_or_result.get("candidate_payload")
        if isinstance(submitted_raw, Mapping):
            submitted = dict(submitted_raw)
        elif set(original) <= set(claim_or_result):
            submitted = {key: claim_or_result[key] for key in original}
        else:
            submitted = original
        expected_target = canonical.get(target)
        original_mismatch = original.get(target) != expected_target
        repaired_target = submitted.get(target) == expected_target
        preserve_matches = all(
            submitted.get(field) == canonical.get(field)
            for field in scenario.preserve_fields
        )
        exact_fields = set(submitted) == set(canonical)
        semantic_fields = {
            field
            for field in canonical
            if field
            in {
                "source_id",
                "definition_id",
                "time_basis",
                "frequency",
                "unit",
                "currency",
                "entity_scope",
                "metric_scope",
                "period_scope",
            }
        }
        semantic_mismatches: dict[str, list[str]] = {}
        for field in sorted(semantic_fields):
            observed = sorted(
                {
                    str(value)
                    for item in evidence
                    if (value := _semantic_candidate_value(item, field)) not in (None, "")
                }
            )
            expected_semantics = canonical[field]
            if isinstance(expected_semantics, list):
                supported = observed == [str(value) for value in expected_semantics]
            else:
                supported = bool(observed) and all(
                    value == str(expected_semantics) for value in observed
                )
            if not supported:
                semantic_mismatches[field] = observed
        conflicts: list[dict[str, Any]] = []
        if not original_mismatch:
            conflicts.append({"type": "candidate_not_actually_corrupted", "field": target})
        if not repaired_target:
            conflicts.append(
                {
                    "type": "candidate_field_mismatch",
                    "field": target,
                    "candidate_value": submitted.get(target),
                    "canonical_value": expected_target,
                }
            )
        if not preserve_matches or not exact_fields:
            conflicts.append(
                {
                    "type": "candidate_unaffected_field_changed",
                    "required_preserve_fields": list(scenario.preserve_fields),
                }
            )
        if semantic_mismatches:
            conflicts.append(
                {
                    "type": "candidate_semantic_context_unsupported",
                    "mismatches": semantic_mismatches,
                }
            )
        repair_verified = (
            original_mismatch
            and repaired_target
            and preserve_matches
            and exact_fields
            and not semantic_mismatches
        )
        return (
            {
                "localized": original_mismatch,
                "repair_verified": repair_verified,
                "target_field": target,
                "preserve_fields": list(scenario.preserve_fields),
                "submitted_candidate": submitted,
                "canonical_target_value": expected_target,
                "replay_operation_ref": latest.operation_ref,
                "semantic_context_verified": not semantic_mismatches,
            },
            conflicts,
        )

    def _completion_state(
        self,
        scenario: FinanceCapabilityMechanismScenario,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        selected = tuple(self._by_id[item] for item in sorted(self._selected_ids))
        resolved: list[str] = []
        missing: list[str] = []
        for role in scenario.required_roles:
            matched = any(_matches_completion_role(item, role) for item in selected)
            (resolved if matched else missing).append(role.role_id)
        complete = not missing
        state = {
            "complete": complete,
            "resolved_role_ids": resolved,
            "missing_role_ids": missing,
            "redundant_action_policy": scenario.redundant_action_policy,
            "redundant_action_cost_applied": False,
        }
        conflicts = (
            []
            if complete
            else [{"type": "required_roles_incomplete", "missing_role_ids": missing}]
        )
        return state, conflicts

    def _selected_evidence(
        self,
        evidence_ids: tuple[str, ...],
    ) -> tuple[EvidenceItem, ...]:
        unknown = set(evidence_ids) - set(self._by_id)
        if unknown:
            raise ValueError(f"Evidence IDs are unknown: {sorted(unknown)}")
        unselected = set(evidence_ids) - self._selected_ids
        if unselected:
            raise ValueError(f"Evidence IDs were not selected: {sorted(unselected)}")
        return tuple(self._by_id[item] for item in evidence_ids)


def _semantic_candidate_value(item: EvidenceItem, field: str) -> Any:
    if field == "source_id":
        return item.source.source_id
    if field == "definition_id":
        return item.definition.definition_id
    if field == "time_basis":
        return item.temporal_context.basis
    if field == "frequency":
        return item.temporal_context.frequency
    if field == "unit":
        return getattr(item.payload, "unit", None)
    if field == "currency":
        return getattr(item.payload, "currency", None)
    if field == "entity_scope":
        return item.subject.subject_id
    if field == "metric_scope":
        return item.predicate
    if field == "period_scope":
        return item.temporal_context.label
    raise ValueError(f"unknown semantic candidate field: {field}")


def _matches_completion_role(
    item: EvidenceItem,
    role: FinanceCompletionRole,
) -> bool:
    return (
        _matches_subject(item, role.subject_alias)
        and _matches_metric(item, role.metric_alias)
        and _matches_exact(item.temporal_context.label or "", role.period_label)
        and _matches_public_filters(item, role.public_filters)
    )


def _required_string(arguments: dict[str, Any], field: str) -> str:
    value = arguments.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a nonempty string")
    return value.strip()


def _required_int(
    arguments: dict[str, Any],
    field: str,
    *,
    minimum: int,
    maximum: int,
) -> int:
    value = arguments.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    if value < minimum or value > maximum:
        raise ValueError(f"{field} must be between {minimum} and {maximum}")
    return value


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value in (None, ()):
        return ()
    if not isinstance(value, (list, tuple)):
        raise ValueError("optional text filters must be arrays")
    output = tuple(str(item).strip() for item in value if str(item).strip())
    if len(output) != len(set(output)):
        raise ValueError("optional text filters contain duplicates")
    return output


def _evidence_id_tuple(value: Any) -> tuple[str, ...]:
    evidence_ids = _string_tuple(value)
    if not evidence_ids:
        raise ValueError("evidence_ids must be a nonempty array")
    return evidence_ids


def _failed(
    code: str,
    message: str,
    *,
    result: dict[str, Any] | None = None,
) -> AgentToolResult:
    return AgentToolResult(
        status="failed",
        result=result or {},
        error_code=code,
        error_message=message,
    )


def _typed_recovery_retry_contract(
    matches: tuple[EvidenceItem, ...],
    filters: dict[str, Any],
) -> dict[str, Any]:
    item = min(matches, key=lambda value: value.evidence_id)
    supported = (
        ("source_id", item.source.source_id),
        ("definition_id", item.definition.definition_id),
        ("time_basis", item.temporal_context.basis),
        ("frequency", item.temporal_context.frequency),
        ("subject_type", item.subject.subject_type),
        ("source_authority", item.source.authority.value),
        ("unit", getattr(item.payload, "unit", None)),
        ("currency", getattr(item.payload, "currency", None)),
    )
    patch: dict[str, Any] = {}
    for key, value in supported:
        if value not in (None, "") and filters.get(key) != value:
            patch = {"public_filters": {**filters, key: value}}
            break
    if not patch:
        patch = {"subject_alias": item.subject.subject_id}
    return {
        "policy": ARGUMENT_PATCH_REQUIRED_POLICY,
        "maximum_identical_replays": 0,
        "suggested_argument_patch": patch,
    }


def _tokens(value: str) -> set[str]:
    return {
        item.casefold()
        for item in _TOKEN_PATTERN.findall(value)
        if len(item) > 1 or "\u4e00" <= item <= "\u9fff"
    }


def _normalize_text(value: str) -> str:
    return " ".join(_TOKEN_PATTERN.findall(value.casefold()))


def _matches_text(value: str, aliases: tuple[str, ...]) -> bool:
    normalized_value = _normalize_text(value)
    return any(
        (normalized_alias := _normalize_text(alias))
        and (normalized_alias in normalized_value or bool(_tokens(alias) & _tokens(value)))
        for alias in aliases
    )


def _matches_exact(value: str, expected: str) -> bool:
    return _normalize_text(value) == _normalize_text(expected)


def _matches_subject(item: EvidenceItem, alias: str) -> bool:
    normalized = _normalize_text(alias)
    aliases = {
        _normalize_text(item.subject.subject_id),
        _normalize_text(item.subject.name),
    }
    aliases.update(
        _normalize_text(item.subject.subject_id[: -len(suffix)])
        for suffix in _PUBLIC_SUBJECT_ID_SUFFIXES
        if item.subject.subject_id.endswith(suffix)
    )
    return normalized in aliases


def _matches_metric(item: EvidenceItem, alias: str) -> bool:
    normalized = _normalize_text(alias)
    attributes = item.definition.attributes
    candidates = {
        item.predicate,
        str(attributes.get("metric_name") or ""),
        str(attributes.get("raw_concept_name") or ""),
        item.definition.definition_id or "",
    }
    return normalized in {_normalize_text(value) for value in candidates if value}


def _matches_source(item: EvidenceItem, filters: tuple[str, ...]) -> bool:
    return _matches_text(
        " ".join(
            (
                item.source.source_id,
                item.source.name,
                item.source.provider or "",
                item.source.authority.value,
            )
        ),
        filters,
    )


def _metric_text(item: EvidenceItem) -> str:
    attributes = item.definition.attributes
    return " ".join(
        (
            item.predicate,
            str(attributes.get("metric_name") or ""),
            str(attributes.get("raw_concept_name") or ""),
            item.definition.definition_id or "",
            item.definition.text or "",
        )
    )


def _search_text(item: EvidenceItem) -> str:
    return " ".join(
        (
            item.subject.subject_id,
            item.subject.name,
            item.subject.subject_type,
            _metric_text(item),
            item.temporal_context.label or "",
            item.temporal_context.basis or "",
            item.temporal_context.frequency or "",
            item.source.source_id,
            item.source.name,
            item.source.provider or "",
            item.source.authority.value,
        )
    )


def _matches_public_filters(item: EvidenceItem, filters: dict[str, Any]) -> bool:
    supported = {
        "source_id": item.source.source_id,
        "source_authority": item.source.authority.value,
        "unit": getattr(item.payload, "unit", None),
        "currency": getattr(item.payload, "currency", None),
        "definition_id": item.definition.definition_id,
        "time_basis": item.temporal_context.basis,
        "frequency": item.temporal_context.frequency,
        "subject_type": item.subject.subject_type,
    }
    unknown = set(filters) - set(supported)
    if unknown:
        raise ValueError(
            f"unsupported public_filters: {sorted(unknown)}; allowed scalar keys are "
            f"{sorted(supported)}; use {{}} when no exact filter is needed"
        )
    return all(value in (None, "") or supported[key] == value for key, value in filters.items())


def _public_locator(item: EvidenceItem) -> str:
    return f"archive://source/{item.source_locator.locator_hash}"


def _evidence_summary(
    item: EvidenceItem,
    *,
    public_locator: str,
) -> dict[str, Any]:
    return {
        "evidence_id": item.evidence_id,
        "public_locator": public_locator,
        "subject": {
            "subject_id": item.subject.subject_id,
            "name": item.subject.name,
            "type": item.subject.subject_type,
        },
        "metric": {
            "predicate": item.predicate,
            "name": item.definition.attributes.get("metric_name"),
            "definition_id": item.definition.definition_id,
        },
        "period": item.temporal_context.label,
        "source": {
            "source_id": item.source.source_id,
            "name": item.source.name,
            "authority": item.source.authority.value,
        },
    }


def _public_fact(item: EvidenceItem) -> dict[str, Any]:
    return {
        **_evidence_summary(item, public_locator=_public_locator(item)),
        "payload": item.payload.model_dump(mode="json", exclude_none=True),
        "time_basis": item.temporal_context.basis,
        "frequency": item.temporal_context.frequency,
        "source_locator_hash": item.source_locator.locator_hash,
        "provenance_hash": _provenance_hash(item),
    }


def _scalar_value(item: EvidenceItem) -> str:
    if not isinstance(item.payload, ScalarObservation):
        raise ValueError(f"Evidence is not a scalar observation: {item.evidence_id}")
    return format(Decimal(str(item.payload.value)), "f")


def _provenance_complete(item: EvidenceItem) -> bool:
    return bool(
        item.evidence_version_id
        and item.provenance.adapter_id
        and item.provenance.archive_id
        and item.provenance.source_record_id
        and item.source_locator.locator_hash
    )


def _provenance_hash(item: EvidenceItem) -> str:
    return canonical_hash(
        {
            "evidence_version_id": item.evidence_version_id,
            "source_locator": item.source_locator,
            "provenance": item.provenance,
        },
        prefix="finance_agent_evidence_provenance:",
    )


def _provenance_hashes(evidence: tuple[EvidenceItem, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(_provenance_hash(item) for item in evidence))


def _select_mapping_value(value: dict[str, Any], selector: str) -> Any:
    current: Any = value
    for segment in selector.split("."):
        if not isinstance(current, dict) or segment not in current:
            raise ValueError(f"operation selector is invalid: {selector}")
        current = current[segment]
    return current


def _find_operation_refs(value: Any) -> set[str]:
    if isinstance(value, dict):
        return {
            *(str(item) for item in value.values() if _is_operation_ref(item)),
            *(ref for item in value.values() for ref in _find_operation_refs(item)),
        }
    if isinstance(value, (list, tuple)):
        return {ref for item in value for ref in _find_operation_refs(item)}
    return {str(value)} if _is_operation_ref(value) else set()


def _is_operation_ref(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("operation:")
