from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.core.operations.registry import OperationRegistry
from trusted_synthesis.domains.finance.agent_tools import (
    make_finance_archive_agent_tool_manifest,
)
from trusted_synthesis.domains.finance.interactive_agent_runtime import (
    FinanceArchiveInteractiveToolRuntime,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.tools import (
    ARGUMENT_PATCH_REQUIRED_POLICY,
    PREREQUISITE_ACTION_REQUIRED_POLICY,
    AgentToolCall,
    AgentToolEnvironmentManifest,
    AgentToolResult,
    make_agent_tool_environment_manifest,
)

FINANCE_SUBMECHANISM_SCENARIO_VERSION = "finance_capability_submechanism_scenario.v10"
FINANCE_SUBMECHANISM_RUNTIME_VERSION = "finance_capability_submechanism_runtime.v12"
FINANCE_PUBLIC_DECISION_CONTRACT_VERSION = "finance_capability_decision_contract.v6"
FINANCE_STOPPING_SHAPE_DECISION_VERSION = "finance_stopping_shape_decision_contract.v2"
FINANCE_STOPPING_SHAPE_DECISION_V1_VERSION = "finance_stopping_shape_decision_contract.v1"
FINANCE_SUBMECHANISM_ORACLE_KEY = "v25_25_capability_submechanism_scenario"

SubmechanismKind = Literal[
    "parameter_field_correction",
    "missing_prerequisite_evidence",
    "tool_switch",
    "operation_reference_repair",
    "selector_scope_correction",
    "unit_error",
    "source_definition_error",
    "local_calculation_error",
    "insufficient_evidence",
    "entity_scope_error",
    "retrieval_failure",
    "argument_failure",
    "calculation_prerequisite_failure",
    "evidence_conflict",
    "empty_result_tool_fallback",
    "incomplete_continue",
    "post_complete_error_risk",
    "post_complete_cost",
    "unresolved_conflict_cannot_stop",
    "uncertain_source_coverage",
]

_CANDIDATE_KINDS = frozenset(
    {
        "unit_error",
        "source_definition_error",
        "local_calculation_error",
        "entity_scope_error",
    }
)
_COMPLETENESS_KINDS = frozenset(
    {
        "insufficient_evidence",
        "incomplete_continue",
        "post_complete_error_risk",
        "post_complete_cost",
        "uncertain_source_coverage",
    }
)
_PARTIAL_SUPPORT_KINDS = frozenset({"insufficient_evidence", "incomplete_continue"})
_CONFLICT_KINDS = frozenset(
    {
        "evidence_conflict",
        "unresolved_conflict_cannot_stop",
    }
)


@dataclass(frozen=True)
class _RuntimePolicy:
    trigger_tool: str
    resolution_tools: tuple[str, ...]
    trigger_error_code: str
    trigger_after_successes: int = 0
    mode: Literal["forced_failure", "candidate", "completeness", "conflict"] = "forced_failure"


_POLICIES: dict[SubmechanismKind, _RuntimePolicy] = {
    "parameter_field_correction": _RuntimePolicy(
        "query_structured_fact", ("query_structured_fact",), "unknown_parameter_field"
    ),
    "missing_prerequisite_evidence": _RuntimePolicy(
        "calculator", ("query_structured_fact",), "missing_prerequisite_evidence"
    ),
    "tool_switch": _RuntimePolicy(
        "search_archive", ("query_structured_fact",), "unsupported_archive_route"
    ),
    "operation_reference_repair": _RuntimePolicy(
        "cross_check_evidence",
        ("cross_check_evidence",),
        "stale_operation_reference",
    ),
    "selector_scope_correction": _RuntimePolicy(
        "query_structured_fact", ("query_structured_fact",), "selector_scope_mismatch"
    ),
    "unit_error": _RuntimePolicy(
        "cross_check_evidence",
        ("cross_check_evidence",),
        "candidate_unit_mismatch",
        mode="candidate",
    ),
    "source_definition_error": _RuntimePolicy(
        "cross_check_evidence",
        ("cross_check_evidence",),
        "source_definition_incompatible",
        mode="candidate",
    ),
    "local_calculation_error": _RuntimePolicy(
        "cross_check_evidence",
        ("cross_check_evidence",),
        "candidate_calculation_mismatch",
        mode="candidate",
    ),
    "insufficient_evidence": _RuntimePolicy(
        "query_structured_fact",
        ("query_structured_fact", "open_document"),
        "candidate_support_incomplete",
        mode="completeness",
    ),
    "entity_scope_error": _RuntimePolicy(
        "cross_check_evidence",
        ("cross_check_evidence",),
        "candidate_entity_scope_mismatch",
        mode="candidate",
    ),
    "retrieval_failure": _RuntimePolicy(
        "query_structured_fact", ("search_archive",), "structured_retrieval_empty"
    ),
    "argument_failure": _RuntimePolicy(
        "query_structured_fact", ("query_structured_fact",), "typed_argument_failure"
    ),
    "calculation_prerequisite_failure": _RuntimePolicy(
        "calculator", ("query_structured_fact",), "calculation_prerequisite_missing"
    ),
    "evidence_conflict": _RuntimePolicy(
        "cross_check_evidence",
        ("normalize_metric_unit_period",),
        "evidence_definition_conflict",
        mode="conflict",
    ),
    "empty_result_tool_fallback": _RuntimePolicy(
        "query_structured_fact", ("search_archive",), "typed_route_empty"
    ),
    "incomplete_continue": _RuntimePolicy(
        "query_structured_fact",
        ("query_structured_fact", "open_document"),
        "evidence_roles_incomplete",
        mode="completeness",
    ),
    "post_complete_error_risk": _RuntimePolicy(
        "cross_check_evidence", (), "verified_completion_state", mode="completeness"
    ),
    "post_complete_cost": _RuntimePolicy(
        "cross_check_evidence", (), "verified_completion_state", mode="completeness"
    ),
    "unresolved_conflict_cannot_stop": _RuntimePolicy(
        "cross_check_evidence",
        ("normalize_metric_unit_period",),
        "evidence_state_conflicted",
        mode="conflict",
    ),
    "uncertain_source_coverage": _RuntimePolicy(
        "cross_check_evidence",
        ("search_archive", "open_document"),
        "source_coverage_uncertain",
        mode="completeness",
    ),
}


class FinanceSubmechanismEvidenceRole(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    role_id: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    subject_alias: str = Field(min_length=1)
    metric_alias: str = Field(min_length=1)
    period_label: str = Field(min_length=1)


class FinanceStoppingResolutionAction(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    tool_id: Literal["normalize_metric_unit_period", "open_document"]
    applicable_when: str = Field(min_length=1)


class FinanceStoppingDependencyOption(BaseModel):
    """Public executable query option without an Oracle correctness label."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    option_id: str = Field(min_length=1)
    tool_id: Literal["query_structured_fact"] = "query_structured_fact"
    subject_alias: str = Field(min_length=1)
    metric_alias: str = Field(min_length=1)
    period_label: str = Field(min_length=1)


class FinanceStoppingShapeDecisionContract(BaseModel):
    """Preregistered public decision state plus Oracle-only scoring identity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_kind: Literal[
        "partial_evidence_count_only",
        "single_conflict_two_action_one_step",
        "standardized_relative_extra_call_cost",
        "dependency_disambiguation_required",
        "single_conflict_semantic_choice_one_step",
        "sealed_terminal_extra_call_cost",
    ]
    missing_role_disclosure: Literal["count_only"] | None = None
    dependency_rule: str | None = Field(default=None, min_length=1)
    dependency_decoy_option: FinanceStoppingDependencyOption | None = None
    conflict_dimensions: tuple[str, ...] = ()
    observed_conflict_signal: str | None = Field(default=None, min_length=1)
    oracle_conflict_dimension: str | None = Field(default=None, min_length=1)
    available_resolution_actions: tuple[FinanceStoppingResolutionAction, ...] = ()
    resolution_step_count: int | None = Field(default=None, ge=1, le=2)
    remaining_call_budget_fraction: float | None = Field(default=None, gt=0, le=1)
    remaining_token_budget_fraction: float | None = Field(default=None, gt=0, le=1)
    terminal_utility_loss: float | None = Field(default=None, gt=0, le=1)
    archive_snapshot_sealed: bool | None = None
    maximum_additional_information_gain: float | None = Field(default=None, ge=0, le=0)
    realized_call_budget_debit_fraction: float | None = Field(default=None, gt=0, le=1)
    realized_token_budget_debit_fraction: float | None = Field(default=None, gt=0, le=1)
    additional_action_rejected: bool | None = None
    schema_version: str = FINANCE_STOPPING_SHAPE_DECISION_VERSION

    @model_serializer(mode="wrap")
    def serialize_contract(self, serializer: Any) -> dict[str, Any]:
        payload = dict(serializer(self))
        if self.schema_version == FINANCE_STOPPING_SHAPE_DECISION_V1_VERSION:
            for field in (
                "dependency_rule",
                "dependency_decoy_option",
                "observed_conflict_signal",
                "oracle_conflict_dimension",
                "archive_snapshot_sealed",
                "maximum_additional_information_gain",
                "realized_call_budget_debit_fraction",
                "realized_token_budget_debit_fraction",
                "additional_action_rejected",
            ):
                payload.pop(field, None)
        return payload

    @model_validator(mode="after")
    def validate_contract(self) -> FinanceStoppingShapeDecisionContract:
        if (
            self.schema_version == FINANCE_STOPPING_SHAPE_DECISION_V1_VERSION
            and self.contract_kind
            in {
                "dependency_disambiguation_required",
                "single_conflict_semantic_choice_one_step",
                "sealed_terminal_extra_call_cost",
            }
        ):
            raise ValueError("Finance Stopping Shape v2 decision uses a v1 schema identity")
        common_absent = (
            self.dependency_rule is None
            and self.dependency_decoy_option is None
            and self.observed_conflict_signal is None
            and self.oracle_conflict_dimension is None
            and self.archive_snapshot_sealed is None
            and self.maximum_additional_information_gain is None
            and self.realized_call_budget_debit_fraction is None
            and self.realized_token_budget_debit_fraction is None
            and self.additional_action_rejected is None
        )
        if self.contract_kind == "partial_evidence_count_only":
            valid = (
                common_absent
                and self.missing_role_disclosure == "count_only"
                and not self.conflict_dimensions
                and not self.available_resolution_actions
                and self.resolution_step_count is None
                and self.remaining_call_budget_fraction is None
                and self.remaining_token_budget_fraction is None
                and self.terminal_utility_loss is None
            )
        elif self.contract_kind == "single_conflict_two_action_one_step":
            valid = (
                common_absent
                and self.missing_role_disclosure is None
                and self.conflict_dimensions == ("source_definition_compatibility",)
                and tuple(
                    (item.tool_id, item.applicable_when)
                    for item in self.available_resolution_actions
                )
                == (
                    (
                        "normalize_metric_unit_period",
                        "source_definition_compatibility is conflicting",
                    ),
                    (
                        "open_document",
                        "source authority or provenance is unresolved",
                    ),
                )
                and self.resolution_step_count == 1
                and self.remaining_call_budget_fraction is None
                and self.remaining_token_budget_fraction is None
                and self.terminal_utility_loss is None
            )
        elif self.contract_kind == "standardized_relative_extra_call_cost":
            valid = (
                common_absent
                and self.missing_role_disclosure is None
                and not self.conflict_dimensions
                and not self.available_resolution_actions
                and self.resolution_step_count is None
                and self.remaining_call_budget_fraction == 0.25
                and self.remaining_token_budget_fraction == 0.20
                and self.terminal_utility_loss == 1.0
            )
        elif self.contract_kind == "dependency_disambiguation_required":
            valid = (
                self.missing_role_disclosure is None
                and self.dependency_rule is not None
                and self.dependency_decoy_option is not None
                and not self.conflict_dimensions
                and self.observed_conflict_signal is None
                and self.oracle_conflict_dimension is None
                and not self.available_resolution_actions
                and self.resolution_step_count == 1
                and self.remaining_call_budget_fraction is None
                and self.remaining_token_budget_fraction is None
                and self.terminal_utility_loss is None
                and self.archive_snapshot_sealed is None
                and self.maximum_additional_information_gain is None
                and self.realized_call_budget_debit_fraction is None
                and self.realized_token_budget_debit_fraction is None
                and self.additional_action_rejected is None
            )
        elif self.contract_kind == "single_conflict_semantic_choice_one_step":
            public_text = " ".join(
                (
                    self.observed_conflict_signal or "",
                    *(item.applicable_when for item in self.available_resolution_actions),
                )
            ).lower()
            valid = (
                self.missing_role_disclosure is None
                and self.dependency_rule is None
                and self.dependency_decoy_option is None
                and not self.conflict_dimensions
                and self.observed_conflict_signal is not None
                and self.oracle_conflict_dimension == "source_definition_compatibility"
                and tuple(item.tool_id for item in self.available_resolution_actions)
                == ("normalize_metric_unit_period", "open_document")
                and self.resolution_step_count == 1
                and "source_definition_compatibility" not in public_text
                and self.remaining_call_budget_fraction is None
                and self.remaining_token_budget_fraction is None
                and self.terminal_utility_loss is None
                and self.archive_snapshot_sealed is None
                and self.maximum_additional_information_gain is None
                and self.realized_call_budget_debit_fraction is None
                and self.realized_token_budget_debit_fraction is None
                and self.additional_action_rejected is None
            )
        else:
            valid = (
                self.missing_role_disclosure is None
                and self.dependency_rule is None
                and self.dependency_decoy_option is None
                and not self.conflict_dimensions
                and self.observed_conflict_signal is None
                and self.oracle_conflict_dimension is None
                and not self.available_resolution_actions
                and self.resolution_step_count is None
                and self.remaining_call_budget_fraction is None
                and self.remaining_token_budget_fraction is None
                and self.terminal_utility_loss == 1.0
                and self.archive_snapshot_sealed is True
                and self.maximum_additional_information_gain == 0.0
                and self.realized_call_budget_debit_fraction == 0.25
                and self.realized_token_budget_debit_fraction == 0.20
                and self.additional_action_rejected is True
            )
        if not valid:
            raise ValueError("Finance Stopping Shape decision contract is inconsistent")
        return self


class FinanceSubmechanismScenario(BaseModel):
    """Oracle-frozen Host intervention with only public behavior exposed at runtime."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scenario_id: str = Field(min_length=1)
    submechanism_id: str = Field(min_length=1)
    parent_mechanism_id: str = Field(min_length=1)
    intervention_kind: SubmechanismKind
    expected_host_events: tuple[str, str]
    evidence_roles: tuple[FinanceSubmechanismEvidenceRole, ...] = Field(min_length=1)
    untrusted_candidate: dict[str, Any] | None = None
    canonical_candidate: dict[str, Any] | None = None
    repair_target_field: str | None = None
    public_resolution_hint: str = Field(min_length=1)
    stopping_shape_decision_contract: FinanceStoppingShapeDecisionContract | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    schema_version: str = FINANCE_SUBMECHANISM_SCENARIO_VERSION

    @model_validator(mode="after")
    def validate_scenario(self) -> FinanceSubmechanismScenario:
        if self.intervention_kind not in _POLICIES:
            raise ValueError("Finance submechanism has no registered Runtime policy")
        if len({item.role_id for item in self.evidence_roles}) != len(self.evidence_roles):
            raise ValueError("Finance submechanism duplicates an Evidence role")
        if len({item.evidence_id for item in self.evidence_roles}) != len(self.evidence_roles):
            raise ValueError("Finance submechanism duplicates required Evidence")
        candidate = self.intervention_kind in _CANDIDATE_KINDS
        candidate_fields_present = all(
            item is not None
            for item in (
                self.untrusted_candidate,
                self.canonical_candidate,
                self.repair_target_field,
            )
        )
        if candidate != candidate_fields_present:
            raise ValueError("Finance candidate submechanism payload is inconsistent")
        decision = self.stopping_shape_decision_contract
        if decision is not None:
            expected_kind = {
                "partial_evidence_count_only": "incomplete_continue",
                "single_conflict_two_action_one_step": "evidence_conflict",
                "standardized_relative_extra_call_cost": "post_complete_cost",
                "dependency_disambiguation_required": "incomplete_continue",
                "single_conflict_semantic_choice_one_step": "evidence_conflict",
                "sealed_terminal_extra_call_cost": "post_complete_cost",
            }[decision.contract_kind]
            if self.intervention_kind != expected_kind:
                raise ValueError("Stopping Shape decision contract uses the wrong Runtime kind")
        if candidate:
            assert self.untrusted_candidate is not None
            assert self.canonical_candidate is not None
            assert self.repair_target_field is not None
            if set(self.untrusted_candidate) != set(self.canonical_candidate):
                raise ValueError("Finance candidate fields differ from canonical fields")
            mismatches = {
                key
                for key in self.canonical_candidate
                if self.canonical_candidate[key] != self.untrusted_candidate[key]
            }
            if mismatches != {self.repair_target_field}:
                raise ValueError("Finance candidate must contain exactly one local error")
        if len(set(self.expected_host_events)) != 2:
            raise ValueError("Finance submechanism needs distinct observe and resolve events")
        if self.scenario_id != finance_submechanism_scenario_id(self):
            raise ValueError("Finance submechanism scenario identity is invalid")
        return self


def make_finance_submechanism_scenario(
    *,
    submechanism_id: str,
    parent_mechanism_id: str,
    intervention_kind: SubmechanismKind,
    expected_host_events: tuple[str, str],
    evidence_roles: tuple[FinanceSubmechanismEvidenceRole, ...],
    public_resolution_hint: str,
    untrusted_candidate: Mapping[str, Any] | None = None,
    canonical_candidate: Mapping[str, Any] | None = None,
    repair_target_field: str | None = None,
    stopping_shape_decision_contract: FinanceStoppingShapeDecisionContract | None = None,
) -> FinanceSubmechanismScenario:
    values = {
        "submechanism_id": submechanism_id,
        "parent_mechanism_id": parent_mechanism_id,
        "intervention_kind": intervention_kind,
        "expected_host_events": expected_host_events,
        "evidence_roles": evidence_roles,
        "untrusted_candidate": dict(untrusted_candidate) if untrusted_candidate else None,
        "canonical_candidate": dict(canonical_candidate) if canonical_candidate else None,
        "repair_target_field": repair_target_field,
        "public_resolution_hint": public_resolution_hint,
        "stopping_shape_decision_contract": stopping_shape_decision_contract,
        "schema_version": FINANCE_SUBMECHANISM_SCENARIO_VERSION,
    }
    provisional = FinanceSubmechanismScenario.model_construct(scenario_id="pending", **values)
    return FinanceSubmechanismScenario(
        scenario_id=finance_submechanism_scenario_id(provisional), **values
    )


def finance_submechanism_scenario_id(value: FinanceSubmechanismScenario) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"scenario_id"}),
        prefix="finance_capability_submechanism_scenario:",
    )


def submechanism_scenario_from_oracle(
    selection_contract: Mapping[str, Any],
) -> FinanceSubmechanismScenario | None:
    raw = selection_contract.get(FINANCE_SUBMECHANISM_ORACLE_KEY)
    return FinanceSubmechanismScenario.model_validate(raw) if raw is not None else None


def finance_submechanism_runtime_snapshot_hash(
    corpus_hash: str,
    scenario: FinanceSubmechanismScenario,
) -> str:
    return canonical_hash(
        {
            "corpus_hash": corpus_hash,
            "scenario": scenario,
            "runtime_version": FINANCE_SUBMECHANISM_RUNTIME_VERSION,
            "policy_manifest": submechanism_policy_manifest(),
        },
        prefix="finance_capability_submechanism_runtime_snapshot:",
    )


def submechanism_policy_manifest() -> dict[str, dict[str, Any]]:
    return {
        key: {
            "trigger_tool": value.trigger_tool,
            "resolution_tools": value.resolution_tools,
            "trigger_error_code": value.trigger_error_code,
            "trigger_after_successes": value.trigger_after_successes,
            "mode": value.mode,
        }
        for key, value in sorted(_POLICIES.items())
    }


class FinanceCapabilitySubmechanismRuntime:
    """Composition layer that adds one typed intervention to the frozen Finance tools."""

    def __init__(
        self,
        corpus: EvidenceCorpus,
        manifest: AgentToolEnvironmentManifest,
        *,
        scenario: FinanceSubmechanismScenario,
        registry: OperationRegistry | None = None,
    ) -> None:
        expected_snapshot = finance_submechanism_runtime_snapshot_hash(corpus.corpus_hash, scenario)
        if manifest.snapshot_hash != expected_snapshot:
            raise ValueError("Finance submechanism Runtime snapshot differs from its scenario")
        internal_manifest = make_finance_archive_agent_tool_manifest(
            environment_id=f"{manifest.environment_id}:base",
            corpus_id=corpus.corpus_id,
            corpus_hash=corpus.corpus_hash,
            archive_snapshot_id=manifest.snapshot_id,
            archive_snapshot_hash=corpus.corpus_hash,
            maximum_tool_calls=manifest.maximum_tool_calls,
            maximum_failed_tool_calls=manifest.maximum_failed_tool_calls,
            maximum_total_observation_bytes=manifest.maximum_total_observation_bytes,
            tool_timeout_seconds=manifest.tool_timeout_seconds,
        )
        self._manifest = manifest
        self._base = FinanceArchiveInteractiveToolRuntime(
            corpus, internal_manifest, registry=registry
        )
        self._scenario = scenario
        self._policy = _POLICIES[scenario.intervention_kind]
        self._trigger_observed = False
        self._resolution_observed = False
        self._trigger_call: AgentToolCall | None = None
        self._successful_by_tool: dict[str, int] = {}
        self._normalization_observed = False
        self._document_opened = False
        self._verified_complete = False
        self._event_log: list[str] = []

    @property
    def manifest(self) -> AgentToolEnvironmentManifest:
        return self._manifest

    @property
    def scenario(self) -> FinanceSubmechanismScenario:
        return self._scenario

    @property
    def verification_complete(self) -> bool:
        return self._verified_complete

    @property
    def event_log(self) -> tuple[str, ...]:
        return tuple(self._event_log)

    @property
    def discovered_evidence_ids(self) -> tuple[str, ...]:
        return self._base.discovered_evidence_ids

    @property
    def selected_evidence_ids(self) -> tuple[str, ...]:
        return self._base.selected_evidence_ids

    @property
    def operation_refs(self) -> tuple[str, ...]:
        return self._base.operation_refs

    def evidence_item(self, evidence_id: str) -> EvidenceItem:
        try:
            return self._base._by_id[evidence_id]
        except KeyError as exc:
            raise ValueError(f"Finance submechanism Evidence is unknown: {evidence_id}") from exc

    def execute(self, call: AgentToolCall) -> AgentToolResult:
        if self._verified_complete:
            return self._post_completion_rejection()
        kind = self._scenario.intervention_kind
        if self._policy.mode == "forced_failure":
            result = self._execute_forced_failure(call)
        elif self._policy.mode == "candidate":
            result = self._execute_candidate(call)
        elif self._policy.mode == "completeness":
            result = self._execute_completeness(call)
        else:
            result = self._execute_conflict(call)
        if result.status == "succeeded":
            self._successful_by_tool[call.tool_id] = (
                self._successful_by_tool.get(call.tool_id, 0) + 1
            )
            if call.tool_id == "normalize_metric_unit_period":
                self._normalization_observed = True
            if call.tool_id == "open_document":
                self._document_opened = True
        if kind in {"post_complete_error_risk", "post_complete_cost"} and (
            self._resolution_observed
        ):
            self._verified_complete = True
        return result

    def _execute_forced_failure(self, call: AgentToolCall) -> AgentToolResult:
        if not self._trigger_observed and call.tool_id == self._policy.trigger_tool:
            prior = self._successful_by_tool.get(call.tool_id, 0)
            if prior >= self._policy.trigger_after_successes:
                self._observe_trigger(call)
                return self._typed_failure()
        if self._trigger_observed and not self._resolution_observed:
            if call.tool_id not in self._policy.resolution_tools:
                return self._resolution_required_failure()
            if (
                self._trigger_call is not None
                and call.tool_id == self._trigger_call.tool_id
                and call.arguments == self._trigger_call.arguments
                and self._scenario.intervention_kind != "operation_reference_repair"
            ):
                return self._argument_patch_failure()
            result = self._base.execute(call)
            if result.status == "succeeded":
                self._observe_resolution()
                return self._with_resolution_event(result)
            return result
        return self._base.execute(call)

    def _execute_candidate(self, call: AgentToolCall) -> AgentToolResult:
        if not self._trigger_observed and call.tool_id == self._policy.trigger_tool:
            base = self._base.execute(call)
            if base.status == "failed":
                return base
            self._observe_trigger(call)
            return self._candidate_mismatch_result(call)
        if self._trigger_observed and not self._resolution_observed:
            if call.tool_id not in self._policy.resolution_tools:
                return self._resolution_required_failure()
            if not self._candidate_repair_matches(call.arguments):
                return self._candidate_still_invalid_result(call)
            result = self._base.execute(call)
            if result.status == "succeeded" and bool(result.result.get("verified")):
                self._observe_resolution()
                return self._with_candidate_report(result, repaired=True)
            return result
        return self._base.execute(call)

    def _execute_completeness(self, call: AgentToolCall) -> AgentToolResult:
        kind = self._scenario.intervention_kind
        selected = set(self._base.selected_evidence_ids)
        required = {item.evidence_id for item in self._scenario.evidence_roles}
        complete = required <= selected
        if kind in _PARTIAL_SUPPORT_KINDS:
            if not self._trigger_observed:
                result = self._base.execute(call)
                selected = set(self._base.selected_evidence_ids)
                if result.status == "succeeded" and selected and not required <= selected:
                    self._observe_trigger(call)
                    return self._with_partial_selection_state(result)
                return result
            if not complete:
                if call.tool_id not in self._policy.resolution_tools:
                    return self._resolution_required_failure()
                result = self._base.execute(call)
                if result.status == "succeeded":
                    selected = set(self._base.selected_evidence_ids)
                    if required <= selected:
                        self._observe_resolution()
                        return self._with_resolution_event(result)
                    return self._with_partial_selection_state(result)
                return result
        if (
            kind == "uncertain_source_coverage"
            and self._trigger_observed
            and not self._resolution_observed
        ):
            if call.tool_id == "search_archive":
                return self._base.execute(call)
            if call.tool_id != "open_document":
                return self._resolution_required_failure()
            result = self._base.execute(call)
            if result.status == "succeeded":
                self._observe_resolution()
                return self._with_resolution_event(result)
            return result
        if kind == "uncertain_source_coverage" and complete and not self._document_opened:
            if call.tool_id == "cross_check_evidence":
                self._observe_trigger(call)
                return self._incomplete_result(call, conflict_type="source_coverage_uncertain")
            return self._base.execute(call)
        if call.tool_id == "cross_check_evidence" and complete:
            result = self._base.execute(call)
            if result.status == "succeeded" and bool(result.result.get("verified")):
                if not self._trigger_observed:
                    self._observe_trigger(call)
                if not self._resolution_observed:
                    self._observe_resolution()
                return self._with_completion_state(result, complete=True)
            return result
        return self._base.execute(call)

    def _execute_conflict(self, call: AgentToolCall) -> AgentToolResult:
        if not self._trigger_observed and call.tool_id == "cross_check_evidence":
            base = self._base.execute(call)
            if base.status == "failed":
                return base
            self._observe_trigger(call)
            return self._conflict_result(base)
        if self._trigger_observed and not self._normalization_observed:
            if call.tool_id != "normalize_metric_unit_period":
                return self._resolution_required_failure()
            result = self._base.execute(call)
            decision = self._scenario.stopping_shape_decision_contract
            if (
                result.status == "succeeded"
                and decision is not None
                and decision.contract_kind
                in {
                    "single_conflict_two_action_one_step",
                    "single_conflict_semantic_choice_one_step",
                }
            ):
                self._observe_resolution()
                return self._with_resolution_event(result)
            return result
        if self._trigger_observed and not self._resolution_observed:
            if call.tool_id != "cross_check_evidence":
                return self._resolution_required_failure(
                    code="post_resolution_cross_check_required"
                )
            result = self._base.execute(call)
            if result.status == "succeeded" and bool(result.result.get("verified")):
                self._observe_resolution()
                return self._with_resolution_event(result)
            return result
        return self._base.execute(call)

    def _observe_trigger(self, call: AgentToolCall) -> None:
        if not self._trigger_observed:
            self._trigger_observed = True
            self._trigger_call = call
            self._event_log.append(self._scenario.expected_host_events[0])

    def _observe_resolution(self) -> None:
        if not self._resolution_observed:
            self._resolution_observed = True
            self._event_log.append(self._scenario.expected_host_events[1])

    def _typed_failure(self) -> AgentToolResult:
        return AgentToolResult(
            status="failed",
            result={
                "retry_contract": {
                    "policy": PREREQUISITE_ACTION_REQUIRED_POLICY,
                    "required_next_tools": list(self._policy.resolution_tools),
                    "host_event": self._scenario.expected_host_events[0],
                    "suggested_argument_patch": {
                        "rule": self._scenario.public_resolution_hint,
                        "current_operation_refs": list(self._base.operation_refs),
                    },
                }
            },
            error_code=self._policy.trigger_error_code,
            error_message=self._scenario.public_resolution_hint,
        )

    def _resolution_required_failure(
        self, *, code: str = "submechanism_resolution_action_required"
    ) -> AgentToolResult:
        suggested_patch: dict[str, Any] = {"rule": self._scenario.public_resolution_hint}
        candidate_contract = _public_candidate_submission_contract(self._scenario)
        if candidate_contract is not None:
            suggested_patch["candidate_submission_contract"] = candidate_contract
        retry_contract: dict[str, Any] = {
            "policy": PREREQUISITE_ACTION_REQUIRED_POLICY,
            "suggested_argument_patch": suggested_patch,
        }
        public_tools = self._public_resolution_tools()
        if public_tools:
            retry_contract["required_next_tools"] = public_tools
        required_action = self._required_prerequisite_action()
        if required_action is not None:
            retry_contract["required_prerequisite_action"] = required_action
        return AgentToolResult(
            status="failed",
            result={"retry_contract": retry_contract},
            error_code=code,
            error_message=self._scenario.public_resolution_hint,
        )

    def _required_prerequisite_action(self) -> dict[str, Any] | None:
        kind = self._scenario.intervention_kind
        decision = self._scenario.stopping_shape_decision_contract
        if decision is not None and decision.contract_kind in {
            "single_conflict_two_action_one_step",
            "single_conflict_semantic_choice_one_step",
        }:
            return None
        if kind in {"incomplete_continue", "unresolved_conflict_cannot_stop"}:
            # Stopping probes expose the state but leave action selection to the Agent.
            return None
        if kind in _PARTIAL_SUPPORT_KINDS:
            selected = set(self._base.selected_evidence_ids)
            missing = next(
                (
                    item
                    for item in self._scenario.evidence_roles
                    if item.evidence_id not in selected
                ),
                None,
            )
            if missing is None:
                return None
            return {
                "action": "retrieve_missing_evidence_role",
                "tool_id": "query_structured_fact",
                "arguments": {
                    "subject_alias": missing.subject_alias,
                    "metric_alias": missing.metric_alias,
                    "period_label": missing.period_label,
                    "public_filters": {},
                },
            }
        if kind in _CONFLICT_KINDS:
            selected_ordered = tuple(self._base.selected_evidence_ids)
            if not selected_ordered:
                return None
            first = self.evidence_item(selected_ordered[0])
            return {
                "action": "normalize_selected_evidence",
                "tool_id": "normalize_metric_unit_period",
                "arguments": {
                    "evidence_ids": list(selected_ordered),
                    "target_definition": {
                        "definition_id": first.definition.definition_id,
                        "time_basis": first.temporal_context.basis,
                        "frequency": first.temporal_context.frequency,
                    },
                },
            }
        return None

    def _public_resolution_tools(self) -> list[str]:
        decision = self._scenario.stopping_shape_decision_contract
        if decision is not None and decision.contract_kind in {
            "single_conflict_two_action_one_step",
            "single_conflict_semantic_choice_one_step",
        }:
            return []
        if self._scenario.intervention_kind in {
            "incomplete_continue",
            "unresolved_conflict_cannot_stop",
        }:
            return []
        return list(self._policy.resolution_tools)

    def _argument_patch_failure(self) -> AgentToolResult:
        return AgentToolResult(
            status="failed",
            result={
                "retry_contract": {
                    "policy": ARGUMENT_PATCH_REQUIRED_POLICY,
                    "required_next_tools": list(self._policy.resolution_tools),
                    "suggested_argument_patch": {"rule": self._scenario.public_resolution_hint},
                }
            },
            error_code="submechanism_argument_not_revised",
            error_message="The resolution repeated the triggering arguments.",
        )

    def _candidate_mismatch_result(self, call: AgentToolCall) -> AgentToolResult:
        evidence_ids = _evidence_ids(call.arguments)
        report = {
            "localized": True,
            "repair_verified": False,
            "target_field": self._scenario.repair_target_field,
            "submitted_candidate": self._scenario.untrusted_candidate,
            "preserve_fields": sorted(
                set(self._scenario.canonical_candidate or {})
                - {str(self._scenario.repair_target_field)}
            ),
            "host_event": self._scenario.expected_host_events[0],
            "submission_contract": _public_candidate_submission_contract(self._scenario),
        }
        if self._policy.trigger_tool == "normalize_metric_unit_period":
            return AgentToolResult(
                status="succeeded",
                result={
                    "normalized_values": [],
                    "compatibility_report": {
                        "compatible": False,
                        "mismatches": {
                            str(self._scenario.repair_target_field): [
                                (self._scenario.untrusted_candidate or {}).get(
                                    str(self._scenario.repair_target_field)
                                )
                            ]
                        },
                        "candidate_repair": report,
                    },
                    "policy_hash": canonical_hash(
                        report, prefix="finance_submechanism_candidate_policy:"
                    ),
                },
                evidence_ids=evidence_ids,
            )
        return AgentToolResult(
            status="succeeded",
            result={
                "verified": False,
                "support": list(evidence_ids),
                "conflicts": [
                    {
                        "type": self._policy.trigger_error_code,
                        "field": self._scenario.repair_target_field,
                    }
                ],
                "verification_hash": canonical_hash(
                    report, prefix="finance_submechanism_candidate_verification:"
                ),
                "candidate_repair": report,
            },
            evidence_ids=evidence_ids,
        )

    def _candidate_still_invalid_result(self, call: AgentToolCall) -> AgentToolResult:
        evidence_ids = _evidence_ids(call.arguments)
        return AgentToolResult(
            status="succeeded",
            result={
                "verified": False,
                "support": list(evidence_ids),
                "conflicts": [{"type": "candidate_repair_not_exact"}],
                "verification_hash": canonical_hash(
                    call.arguments,
                    prefix="finance_submechanism_candidate_repair_rejected:",
                ),
                "candidate_repair": {
                    "localized": True,
                    "repair_verified": False,
                    "target_field": self._scenario.repair_target_field,
                    "submission_contract": _public_candidate_submission_contract(self._scenario),
                },
            },
            evidence_ids=evidence_ids,
        )

    def _candidate_repair_matches(self, arguments: Mapping[str, Any]) -> bool:
        claim = arguments.get("claim_or_result")
        if not isinstance(claim, Mapping):
            return False
        candidate = claim.get("candidate_payload")
        return isinstance(candidate, Mapping) and dict(candidate) == dict(
            self._scenario.canonical_candidate or {}
        )

    def _with_candidate_report(self, result: AgentToolResult, *, repaired: bool) -> AgentToolResult:
        payload = dict(result.result)
        payload["candidate_repair"] = {
            "localized": True,
            "repair_verified": repaired,
            "target_field": self._scenario.repair_target_field,
            "host_event": self._scenario.expected_host_events[1],
        }
        return result.model_copy(update={"result": payload})

    def _incomplete_result(
        self,
        call: AgentToolCall,
        *,
        conflict_type: str = "required_roles_incomplete",
    ) -> AgentToolResult:
        selected = set(self._base.selected_evidence_ids)
        resolved = [
            item.role_id for item in self._scenario.evidence_roles if item.evidence_id in selected
        ]
        missing = [
            item.role_id
            for item in self._scenario.evidence_roles
            if item.evidence_id not in selected
        ]
        evidence_ids = _evidence_ids(call.arguments)
        return AgentToolResult(
            status="succeeded",
            result={
                "verified": False,
                "support": list(evidence_ids),
                "conflicts": [{"type": conflict_type, "missing_role_ids": missing}],
                "verification_hash": canonical_hash(
                    {"selected": sorted(selected), "missing": missing},
                    prefix="finance_submechanism_incomplete_verification:",
                ),
                "completion_state": {
                    "complete": False,
                    "resolved_role_ids": resolved,
                    "missing_role_ids": missing,
                    "host_event": self._scenario.expected_host_events[0],
                },
            },
            evidence_ids=evidence_ids,
        )

    def _dependency_disambiguation_options(
        self,
        selected: set[str],
        decision: FinanceStoppingShapeDecisionContract,
    ) -> tuple[FinanceStoppingDependencyOption, FinanceStoppingDependencyOption]:
        missing = next(
            (item for item in self._scenario.evidence_roles if item.evidence_id not in selected),
            None,
        )
        if missing is None or decision.dependency_decoy_option is None:
            raise ValueError("dependency disambiguation lacks a missing role or decoy")
        correct = FinanceStoppingDependencyOption(
            option_id=canonical_hash(
                {
                    "scenario_id": self._scenario.scenario_id,
                    "evidence_id": missing.evidence_id,
                },
                prefix="finance_stopping_dependency_option:",
            ),
            subject_alias=missing.subject_alias,
            metric_alias=missing.metric_alias,
            period_label=missing.period_label,
        )
        decoy = decision.dependency_decoy_option
        ordered = tuple(
            sorted(
                (correct, decoy),
                key=lambda item: canonical_hash(
                    {
                        "scenario_id": self._scenario.scenario_id,
                        "option_id": item.option_id,
                    },
                    prefix="finance_stopping_dependency_order:",
                ),
            )
        )
        return (ordered[0], ordered[1])

    def _with_partial_selection_state(self, result: AgentToolResult) -> AgentToolResult:
        selected = set(self._base.selected_evidence_ids)
        resolved = [
            item.role_id for item in self._scenario.evidence_roles if item.evidence_id in selected
        ]
        missing = [
            item.role_id
            for item in self._scenario.evidence_roles
            if item.evidence_id not in selected
        ]
        payload = dict(result.result)
        decision = self._scenario.stopping_shape_decision_contract
        completion_state: dict[str, Any] = {
            "complete": False,
            "resolved_role_ids": resolved,
            "missing_role_ids": missing,
            "host_event": self._scenario.expected_host_events[0],
            "required_prerequisite_action": self._required_prerequisite_action(),
        }
        if decision is not None and decision.contract_kind == "partial_evidence_count_only":
            completion_state = {
                "complete": False,
                "resolved_role_count": len(resolved),
                "missing_role_count": len(missing),
                "required_role_count": len(self._scenario.evidence_roles),
                "missing_role_disclosure": "count_only",
                "completeness_rule": (
                    "Infer the unresolved evidence role from the public task contract and "
                    "retrieve it before verification."
                ),
                "host_event": self._scenario.expected_host_events[0],
                "required_prerequisite_action": None,
            }
        elif (
            decision is not None and decision.contract_kind == "dependency_disambiguation_required"
        ):
            options = self._dependency_disambiguation_options(selected, decision)
            completion_state = {
                "complete": False,
                "selected_evidence_count": len(selected),
                "unresolved_candidate_count": len(options),
                "dependency_rule": decision.dependency_rule,
                "candidate_actions": [item.model_dump(mode="json") for item in options],
                "host_event": self._scenario.expected_host_events[0],
                "required_prerequisite_action": None,
            }
        else:
            completion_state["missing_roles"] = [
                {
                    "role_id": item.role_id,
                    "subject_alias": item.subject_alias,
                    "metric_alias": item.metric_alias,
                    "period_label": item.period_label,
                }
                for item in self._scenario.evidence_roles
                if item.evidence_id not in selected
            ]
        payload["completion_state"] = completion_state
        return result.model_copy(update={"result": payload})

    def _with_completion_state(self, result: AgentToolResult, *, complete: bool) -> AgentToolResult:
        payload = dict(result.result)
        kind = self._scenario.intervention_kind
        decision = self._scenario.stopping_shape_decision_contract
        additional_action_assessment: dict[str, Any] = {
            "marginal_cost": "positive" if kind == "post_complete_cost" else "none",
            "evidence_integrity_risk": (
                "elevated" if kind == "post_complete_error_risk" else "none"
            ),
        }
        if (
            decision is not None
            and decision.contract_kind == "standardized_relative_extra_call_cost"
        ):
            additional_action_assessment = {
                "marginal_cost": "standardized_relative",
                "remaining_call_budget_fraction": decision.remaining_call_budget_fraction,
                "remaining_token_budget_fraction": decision.remaining_token_budget_fraction,
                "terminal_utility_loss": decision.terminal_utility_loss,
                "decision_rule": (
                    "When complete=true, finalization strictly dominates any additional call."
                ),
            }
        elif decision is not None and decision.contract_kind == "sealed_terminal_extra_call_cost":
            additional_action_assessment = {
                "archive_snapshot_sealed": decision.archive_snapshot_sealed,
                "maximum_additional_information_gain": (
                    decision.maximum_additional_information_gain
                ),
                "realized_call_budget_debit_fraction": (
                    decision.realized_call_budget_debit_fraction
                ),
                "realized_token_budget_debit_fraction": (
                    decision.realized_token_budget_debit_fraction
                ),
                "terminal_utility_loss": decision.terminal_utility_loss,
                "additional_action_rejected": decision.additional_action_rejected,
                "decision_rule": (
                    "The verified snapshot is sealed: any additional call has zero possible "
                    "information gain and incurs the frozen realized debit."
                ),
            }
        payload["completion_state"] = {
            "complete": complete,
            "resolved_role_ids": [item.role_id for item in self._scenario.evidence_roles],
            "missing_role_ids": [],
            "host_event_sequence": list(self._scenario.expected_host_events),
            "host_event": self._scenario.expected_host_events[1],
            "additional_action_assessment": additional_action_assessment,
        }
        return result.model_copy(update={"result": payload})

    def _conflict_result(self, result: AgentToolResult) -> AgentToolResult:
        payload = dict(result.result)
        payload["verified"] = False
        payload["conflicts"] = [
            {
                "type": self._policy.trigger_error_code,
                "host_event": self._scenario.expected_host_events[0],
            }
        ]
        payload["verification_hash"] = canonical_hash(
            payload, prefix="finance_submechanism_conflict_verification:"
        )
        retry_contract: dict[str, Any] = {
            "policy": PREREQUISITE_ACTION_REQUIRED_POLICY,
            "required_prerequisite_action": self._required_prerequisite_action(),
            "suggested_argument_patch": {"rule": self._scenario.public_resolution_hint},
        }
        public_tools = self._public_resolution_tools()
        if public_tools:
            retry_contract["required_next_tools"] = public_tools
        decision = self._scenario.stopping_shape_decision_contract
        if decision is not None and decision.contract_kind == "single_conflict_two_action_one_step":
            retry_contract["observed_conflict_dimensions"] = list(decision.conflict_dimensions)
            retry_contract["available_resolution_actions"] = [
                item.model_dump(mode="json") for item in decision.available_resolution_actions
            ]
            retry_contract["decision_rule"] = (
                "Select the single action whose applicable_when condition matches the observed "
                "conflict dimension. The applicable action resolves this one-step conflict."
            )
        elif (
            decision is not None
            and decision.contract_kind == "single_conflict_semantic_choice_one_step"
        ):
            retry_contract["observed_conflict_signal"] = decision.observed_conflict_signal
            retry_contract["available_resolution_actions"] = [
                item.model_dump(mode="json") for item in decision.available_resolution_actions
            ]
            retry_contract["decision_rule"] = (
                "Map the observed semantic symptom to the single applicable action. "
                "No internal conflict-field label is available."
            )
        elif self._scenario.intervention_kind == "unresolved_conflict_cannot_stop":
            retry_contract["observed_conflict_dimensions"] = ["source_definition_compatibility"]
            retry_contract["available_resolution_actions"] = (
                self._ordered_conflict_resolution_actions()
            )
            retry_contract["decision_rule"] = (
                "Select the single action whose applicable_when condition matches the observed "
                "conflict dimensions. Do not repeat verification until that action succeeds."
            )
        payload["retry_contract"] = retry_contract
        return result.model_copy(
            update={
                "status": "failed",
                "result": payload,
                "error_code": self._policy.trigger_error_code,
                "error_message": self._scenario.public_resolution_hint,
            }
        )

    def _ordered_conflict_resolution_actions(self) -> list[dict[str, str]]:
        """Vary presentation order without changing the public decision problem."""

        actions = (
            {
                "tool_id": "normalize_metric_unit_period",
                "applicable_when": "source definitions or temporal bases are incompatible",
            },
            {
                "tool_id": "open_document",
                "applicable_when": "source provenance or document coverage is incomplete",
            },
            {
                "tool_id": "query_structured_fact",
                "applicable_when": "a required evidence role is missing",
            },
        )
        return sorted(
            actions,
            key=lambda item: canonical_hash(
                {
                    "scenario_id": self._scenario.scenario_id,
                    "tool_id": item["tool_id"],
                },
                prefix="finance_public_resolution_action_order:",
            ),
        )

    def _with_resolution_event(self, result: AgentToolResult) -> AgentToolResult:
        payload = dict(result.result)
        payload["submechanism_resolution"] = {
            "resolved": True,
            "host_event": self._scenario.expected_host_events[1],
        }
        return result.model_copy(update={"result": payload})

    def _post_completion_rejection(self) -> AgentToolResult:
        kind = self._scenario.intervention_kind
        code = (
            "redundant_action_exposes_error_risk"
            if kind == "post_complete_error_risk"
            else "redundant_action_after_verified_completion"
        )
        message = (
            "The result is already verified; another action introduces a registered error risk."
            if kind == "post_complete_error_risk"
            else "The result is already verified; another action incurs the frozen marginal cost."
        )
        completion_state: dict[str, Any] = {
            "complete": True,
            "redundant_action_cost_applied": True,
        }
        decision = self._scenario.stopping_shape_decision_contract
        if (
            decision is not None
            and decision.contract_kind == "standardized_relative_extra_call_cost"
        ):
            completion_state["terminal_utility_loss"] = decision.terminal_utility_loss
            completion_state["relative_cost_contract_enforced"] = True
        elif decision is not None and decision.contract_kind == "sealed_terminal_extra_call_cost":
            completion_state.update(
                {
                    "archive_snapshot_sealed": decision.archive_snapshot_sealed,
                    "maximum_additional_information_gain": (
                        decision.maximum_additional_information_gain
                    ),
                    "realized_call_budget_debit_fraction": (
                        decision.realized_call_budget_debit_fraction
                    ),
                    "realized_token_budget_debit_fraction": (
                        decision.realized_token_budget_debit_fraction
                    ),
                    "terminal_utility_loss": decision.terminal_utility_loss,
                    "additional_action_rejected": decision.additional_action_rejected,
                    "sealed_cost_contract_enforced": True,
                }
            )
        return AgentToolResult(
            status="failed",
            result={"completion_state": completion_state},
            error_code=code,
            error_message=message,
        )


def make_submechanism_manifest(
    *,
    corpus: EvidenceCorpus,
    scenario: FinanceSubmechanismScenario,
    environment_id: str,
    maximum_tool_calls: int,
    maximum_failed_tool_calls: int,
    maximum_total_observation_bytes: int,
) -> AgentToolEnvironmentManifest:
    base = make_finance_archive_agent_tool_manifest(
        environment_id=environment_id,
        corpus_id=corpus.corpus_id,
        corpus_hash=corpus.corpus_hash,
        archive_snapshot_id=str(corpus.build_id or f"corpus:{corpus.corpus_hash}"),
        archive_snapshot_hash=finance_submechanism_runtime_snapshot_hash(
            corpus.corpus_hash, scenario
        ),
        maximum_tool_calls=maximum_tool_calls,
        maximum_failed_tool_calls=maximum_failed_tool_calls,
        maximum_total_observation_bytes=maximum_total_observation_bytes,
    )
    tools = tuple(
        spec.model_copy(
            update={
                "output_contract": {
                    **spec.output_contract,
                    "submechanism_resolution": (
                        "optional Host-owned typed resolution event emitted only after the "
                        "registered submechanism has been resolved"
                    ),
                    "completion_state": (
                        "optional Host-owned partial or complete Evidence-role state with a "
                        "typed prerequisite action when work must continue"
                    ),
                }
            }
        )
        for spec in base.tools
    )
    return make_agent_tool_environment_manifest(
        environment_id=base.environment_id,
        corpus_id=base.corpus_id,
        corpus_hash=base.corpus_hash,
        snapshot_id=base.snapshot_id,
        snapshot_hash=base.snapshot_hash,
        network_policy=base.network_policy,
        tools=tools,
        maximum_tool_calls=base.maximum_tool_calls,
        maximum_failed_tool_calls=base.maximum_failed_tool_calls,
        maximum_total_observation_bytes=base.maximum_total_observation_bytes,
        tool_timeout_seconds=base.tool_timeout_seconds,
    )


def _evidence_ids(arguments: Mapping[str, Any]) -> tuple[str, ...]:
    raw = arguments.get("evidence_ids")
    if not isinstance(raw, list):
        return ()
    return tuple(dict.fromkeys(str(item) for item in raw if str(item)))


def evidence_roles_from_items(
    items: tuple[EvidenceItem, ...],
) -> tuple[FinanceSubmechanismEvidenceRole, ...]:
    return tuple(
        FinanceSubmechanismEvidenceRole(
            role_id=f"required_{index + 1}",
            evidence_id=item.evidence_id,
            subject_alias=item.subject.subject_id,
            metric_alias=item.predicate,
            period_label=str(item.temporal_context.label),
        )
        for index, item in enumerate(items)
    )


def public_submechanism_contract(
    scenario: FinanceSubmechanismScenario,
) -> dict[str, Any]:
    """Return the behavior-neutral public projection of an Oracle Runtime scenario."""

    contract = {
        "schema_version": FINANCE_PUBLIC_DECISION_CONTRACT_VERSION,
        "contract_type": "typed_host_state_decision",
        "untrusted_candidate": scenario.untrusted_candidate,
        "required_role_count": len(scenario.evidence_roles),
        "host_feedback_contract": {
            "use_only_public_observations": True,
            "treat_completion_and_conflict_state_as_authoritative": True,
            "follow_typed_prerequisite_action_when_present": True,
            "otherwise_select_the_next_action_from_public_tool_schemas": True,
            "stop_only_when_the_observed_state_supports_finalization": True,
        },
        "oracle_mechanism_identity_disclosed": False,
    }
    candidate_contract = _public_candidate_submission_contract(scenario)
    if candidate_contract is not None:
        contract["candidate_submission_contract"] = candidate_contract
    if scenario.stopping_shape_decision_contract is not None:
        decision = scenario.stopping_shape_decision_contract.model_dump(
            mode="json",
            exclude={
                "contract_kind",
                "dependency_decoy_option",
                "oracle_conflict_dimension",
            },
        )
        decision["internal_shape_identity_disclosed"] = False
        contract["stopping_shape_decision_contract"] = decision
    return contract


def _public_candidate_submission_contract(
    scenario: FinanceSubmechanismScenario,
) -> dict[str, Any] | None:
    """Expose the repair payload shape without exposing its canonical value."""

    if scenario.untrusted_candidate is None or scenario.repair_target_field is None:
        return None
    fields = tuple(sorted(scenario.untrusted_candidate))
    return {
        "selector": ["claim_or_result", "candidate_payload"],
        "required_fields": list(fields),
        "localized_field": scenario.repair_target_field,
        "preserve_fields": [field for field in fields if field != scenario.repair_target_field],
        "additional_fields_allowed": False,
        "canonical_value_disclosed": False,
        "value_source": "derive_independently_from_public_evidence_and_tool_observations",
    }


def scenario_debug_summary(scenario: FinanceSubmechanismScenario) -> str:
    return json.dumps(
        public_submechanism_contract(scenario),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
