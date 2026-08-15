from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.domains.finance.capability_submechanism_runtime import (
    FINANCE_SUBMECHANISM_SCENARIO_VERSION,
    FinanceCapabilitySubmechanismRuntime,
    make_submechanism_manifest,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary import (
    MAXIMUM_FAILED_TOOL_CALLS,
    MAXIMUM_OBSERVATION_BYTES,
    MAXIMUM_TOOL_CALLS,
    CapabilityRuntimeArm,
    RuntimeTaskBinding,
    _make_runtime_binding,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary_analysis import (
    CapabilityRolloutOutcome,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary_runner import (
    CapabilityBoundaryRolloutRecord,
    _all_observations,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CapabilitySensitiveTaskArtifact,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_direction_design import (  # noqa: E501
    CapabilitySubmechanismDirectionReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_flash_development import (  # noqa: E501
    SubmechanismBehaviorObservation,
    _make_terminals,
    make_submechanism_behavior_observations,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_population import (  # noqa: E501
    CapabilitySubmechanismPopulation,
    _ReplayCalls,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_cross_population_stable_protocol import (  # noqa: E501
    EXPECTED_POPULATION_COUNT,
    EXPECTED_ROLLOUTS_PER_POPULATION,
    EXPECTED_TASK_COUNT,
    EXPECTED_TASKS_PER_POPULATION,
    STOPPING_SHAPE_MAPPING,
    FinanceCrossPopulationStableProtocol,
    FrozenArtifactReference,
    verify_cross_population_stable_protocol_inputs,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_confirmation import (
    _execute_stage,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_runtime_resolution import (  # noqa: E501
    FailureLayer,
    RuntimeResolutionStage,
    RuntimeTerminalOutcome,
    _load_records,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_pro_flash_agent_pilot import (
    ExplorerArm,
    ExplorerModelContract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stable_submechanism_geometry import (  # noqa: E501
    StableBootstrapSummary,
    StableIdentifiableSubspacePolicy,
    StableSubspaceAlignment,
    StableSubspaceEstimate,
    StableTaskResponse,
    bootstrap_stable_subspace,
    compare_stable_subspaces,
    estimate_stable_subspace,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stable_submechanism_support import (  # noqa: E501
    _population_disjointness,
    _stable_rows,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_boundary_calibration import (  # noqa: E501
    STOPPING_PARENT_ID,
    UNRESOLVED_CONFLICT_ID,
    FinanceStoppingBoundaryCalibrationContract,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.iterative import (
    IterativeAgentProtocolProfile,
    _failed_action_repair_context,
)
from trusted_synthesis.runtime.tools import (
    ARGUMENT_PATCH_REQUIRED_POLICY,
    AgentToolCall,
    AgentToolObservation,
    AgentToolResult,
    make_agent_tool_observation,
)

CROSS_POPULATION_STABLE_CONTRACT_VERSION = "finance_cross_population_stable_support_contract.v1"
CROSS_POPULATION_STABLE_REPORT_VERSION = "finance_cross_population_stable_support_report.v1"
CROSS_POPULATION_STABLE_MANIFEST_VERSION = "finance_cross_population_stable_support_manifest.v1"
CROSS_POPULATION_TYPED_AUDIT_VERSION = "finance_cross_population_typed_context_audit.v1"
CROSS_POPULATION_RESULT_VERSION = "finance_cross_population_stable_result.v1"

REPLICAS = 8
EXPECTED_UNRESOLVED_CONFLICT_ROLLOUTS_PER_POPULATION = REPLICAS

_FORBIDDEN_TYPED_CONTEXT_KEYS = frozenset(
    {
        "arguments",
        "canonical_candidate",
        "correct_action",
        "correct_tool_id",
        "evidence_id",
        "evidence_ids",
        "hidden_program",
        "operation_plan",
        "task_program",
        "target_definition",
    }
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class TypedContextPopulationAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    population_id: str = Field(min_length=1)
    task_artifact_id: str = Field(min_length=1)
    retry_contract_hash: str = Field(min_length=1)
    action_order_signature: str = Field(min_length=1)
    action_count: int = Field(ge=2)
    stopping_shape_coverage_rate: float = Field(ge=0, le=1)
    missing_conflict_dimensions_rejected: bool
    action_order_permutation_accepted: bool
    unavailable_distractor_action_rejected: bool
    latest_typed_prerequisite_survives_repeated_failure: bool
    host_secret_injection_absent: bool
    ready: bool
    schema_version: str = CROSS_POPULATION_TYPED_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> TypedContextPopulationAudit:
        expected = bool(
            self.stopping_shape_coverage_rate == 1.0
            and self.missing_conflict_dimensions_rejected
            and self.action_order_permutation_accepted
            and self.unavailable_distractor_action_rejected
            and self.latest_typed_prerequisite_survives_repeated_failure
            and self.host_secret_injection_absent
        )
        if self.ready != expected:
            raise ValueError("typed-context static audit decision is inconsistent")
        if self.audit_id != typed_context_population_audit_id(self):
            raise ValueError("typed-context static audit identity is invalid")
        return self


class FinanceCrossPopulationStableContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    experiment_label: Literal["finance_v25_35_cross_population_stable_support_development"] = (
        "finance_v25_35_cross_population_stable_support_development"
    )
    stage: RuntimeResolutionStage = RuntimeResolutionStage.RESIDUAL_DEVELOPMENT
    source_protocol: FrozenArtifactReference
    source_calibration_contract: FrozenArtifactReference
    finance_archive_config_path: str = Field(min_length=1)
    finance_archive_config_sha256: str = Field(min_length=64, max_length=64)
    population_references: tuple[FrozenArtifactReference, ...] = Field(
        min_length=EXPECTED_POPULATION_COUNT,
        max_length=EXPECTED_POPULATION_COUNT,
    )
    implementation_manifest: dict[str, str]
    implementation_manifest_hash: str = Field(min_length=1)
    model_contracts: tuple[ExplorerModelContract, ...] = Field(min_length=1, max_length=1)
    protocol_profile: IterativeAgentProtocolProfile
    tasks: tuple[CapabilitySensitiveTaskArtifact, ...] = Field(
        min_length=EXPECTED_TASK_COUNT,
        max_length=EXPECTED_TASK_COUNT,
    )
    task_submechanism_ids: dict[str, str]
    task_parent_mechanism_ids: dict[str, str]
    task_raw_capability_demands: dict[str, dict[str, float]]
    task_instance_ids: dict[str, str]
    task_population_ids: dict[str, str]
    bindings: tuple[RuntimeTaskBinding, ...] = Field(
        min_length=EXPECTED_TASK_COUNT,
        max_length=EXPECTED_TASK_COUNT,
    )
    typed_context_audits: tuple[TypedContextPopulationAudit, ...] = Field(
        min_length=EXPECTED_POPULATION_COUNT,
        max_length=EXPECTED_POPULATION_COUNT,
    )
    replicas: Literal[8] = 8
    requested_rollout_count: Literal[480] = 480
    maximum_model_tokens_per_rollout: int = Field(ge=1)
    maximum_observation_summary_bytes: int = Field(ge=1)
    maximum_public_context_bytes: int = Field(ge=1)
    model_contract_repair_attempts: int = Field(ge=0)
    rollout_identity_tokens: dict[str, str]
    stable_subspace_policy: StableIdentifiableSubspacePolicy
    primary_response_variable: Literal["capability_contract_success"] = (
        "capability_contract_success"
    )
    historical_results_reclassified: Literal[False] = False
    pro_api_call_count: Literal[0] = 0
    beneficiary_screening_authorized: Literal[False] = False
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal["flash_cross_population_stable_development"] = (
        "flash_cross_population_stable_development"
    )
    schema_version: str = CROSS_POPULATION_STABLE_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> FinanceCrossPopulationStableContract:
        if self.stage != RuntimeResolutionStage.RESIDUAL_DEVELOPMENT:
            raise ValueError("cross-population support must remain Development-only")
        if len(self.model_contracts) != 1 or self.model_contracts[0].arm != ExplorerArm.FLASH:
            raise ValueError("cross-population support must remain Flash-only")
        task_ids = {item.artifact_id for item in self.tasks}
        if len(task_ids) != EXPECTED_TASK_COUNT:
            raise ValueError("cross-population task identities are duplicated")
        maps = (
            self.task_submechanism_ids,
            self.task_parent_mechanism_ids,
            self.task_raw_capability_demands,
            self.task_instance_ids,
            self.task_population_ids,
        )
        if any(set(item) != task_ids for item in maps):
            raise ValueError("cross-population task maps are incomplete")
        if {item.task_artifact_id for item in self.bindings} != task_ids:
            raise ValueError("cross-population bindings differ from tasks")
        if len({item.binding_id for item in self.bindings}) != EXPECTED_TASK_COUNT:
            raise ValueError("cross-population binding identities are duplicated")
        population_ids = {item.artifact_id for item in self.population_references}
        if len(population_ids) != EXPECTED_POPULATION_COUNT:
            raise ValueError("cross-population population identities are duplicated")
        population_counts = Counter(self.task_population_ids.values())
        if set(population_counts) != population_ids or set(population_counts.values()) != {
            EXPECTED_TASKS_PER_POPULATION
        }:
            raise ValueError("cross-population task allocation is incomplete")
        if {item.population_id for item in self.typed_context_audits} != population_ids:
            raise ValueError("cross-population typed-context audits are incomplete")
        if not all(item.ready for item in self.typed_context_audits):
            raise ValueError("cross-population typed-context audit failed before API use")
        if len({item.action_order_signature for item in self.typed_context_audits}) < 2:
            raise ValueError("cross-population conflict actions retain one fixed order")
        expected_tokens = {
            f"{binding.binding_id}|{replicate}"
            for binding in self.bindings
            for replicate in range(self.replicas)
        }
        if set(self.rollout_identity_tokens) != expected_tokens:
            raise ValueError("cross-population rollout identities are incomplete")
        if self.implementation_manifest_hash != canonical_hash(
            self.implementation_manifest,
            prefix="finance_cross_population_stable_support_implementation:",
        ):
            raise ValueError("cross-population implementation identity is invalid")
        if self.contract_id != cross_population_stable_contract_id(self):
            raise ValueError("cross-population contract identity is invalid")
        return self


PopulationGateCategory = Literal[
    "runtime", "typed_context", "coverage", "geometry", "stopping_parent"
]


class PopulationStableGate(FrozenModel):
    gate_id: str = Field(min_length=1)
    category: PopulationGateCategory
    observed: float
    requirement: str = Field(min_length=1)
    passed: bool


class TypedContextDynamicSummary(FrozenModel):
    expected_rollout_count: Literal[8] = 8
    trigger_observed_rollout_count: int = Field(ge=0, le=8)
    complete_replay_rollout_count: int = Field(ge=0, le=8)
    complete_replay_rate: float = Field(ge=0, le=1)
    identical_block_count: int = Field(ge=0)
    identical_block_memory_preserved_count: int = Field(ge=0)


class PopulationStableResult(FrozenModel):
    population_id: str = Field(min_length=1)
    task_count: int = Field(ge=0)
    rollout_count: int = Field(ge=0)
    execution_integrity_rate: float = Field(ge=0, le=1)
    terminal_resolution_rate: float = Field(ge=0, le=1)
    api_transport_resolution_rate: float = Field(ge=0, le=1)
    bounded_json_resolution_rate: float = Field(ge=0, le=1)
    observation_replay_rate: float = Field(ge=0, le=1)
    authority_integrity_rate: float = Field(ge=0, le=1)
    runtime_pathology_rate: float = Field(ge=0, le=1)
    l0_l2_failure_count: int = Field(ge=0)
    typed_context: TypedContextDynamicSummary
    stable_estimate: StableSubspaceEstimate
    bootstrap_summary: StableBootstrapSummary
    stopping_parent_information_share: float = Field(ge=0, le=1)
    stopping_parent_bootstrap_lcb: float = Field(ge=0, le=1)
    nonzero_stopping_task_count: int = Field(ge=0)
    gates: tuple[PopulationStableGate, ...] = Field(min_length=20)
    runtime_measurement_ready: bool
    capability_support_admitted: bool
    failure_codes: tuple[str, ...]
    schema_version: str = CROSS_POPULATION_RESULT_VERSION

    @model_validator(mode="after")
    def validate_result(self) -> PopulationStableResult:
        runtime = tuple(
            item for item in self.gates if item.category in {"runtime", "typed_context"}
        )
        support = tuple(
            item for item in self.gates if item.category not in {"runtime", "typed_context"}
        )
        runtime_ready = bool(runtime) and all(item.passed for item in runtime)
        admitted = runtime_ready and bool(support) and all(item.passed for item in support)
        if self.runtime_measurement_ready != runtime_ready:
            raise ValueError("per-population Runtime decision is inconsistent")
        if self.capability_support_admitted != admitted:
            raise ValueError("per-population support decision is inconsistent")
        expected_failures = tuple(item.gate_id for item in self.gates if not item.passed)
        if self.failure_codes != expected_failures:
            raise ValueError("per-population failure codes are inconsistent")
        return self


class CrossPopulationAlignmentResult(FrozenModel):
    left_population_id: str = Field(min_length=1)
    right_population_id: str = Field(min_length=1)
    alignment: StableSubspaceAlignment
    passed: bool


class FinanceCrossPopulationStableReport(FrozenModel):
    report_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    requested_rollout_count: Literal[480] = 480
    recorded_rollout_count: int = Field(ge=0)
    population_results: tuple[PopulationStableResult, ...] = Field(
        min_length=EXPECTED_POPULATION_COUNT,
        max_length=EXPECTED_POPULATION_COUNT,
    )
    pairwise_alignments: tuple[CrossPopulationAlignmentResult, ...] = Field(
        min_length=3, max_length=3
    )
    pooled_diagnostic_estimate: StableSubspaceEstimate
    pooled_diagnostic_bootstrap: StableBootstrapSummary
    pooled_result_used_for_admission: Literal[False] = False
    static_typed_context_audit_passed: bool
    all_population_runtime_ready: bool
    all_population_capability_support_admitted: bool
    cross_population_alignment_ready: bool
    development_admitted: bool
    failure_codes: tuple[str, ...]
    outcome_set_hash: str = Field(min_length=1)
    behavior_set_hash: str = Field(min_length=1)
    api_call_count: int = Field(ge=0)
    total_model_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    discovered_models: tuple[str, ...]
    execution_implementation_manifest_hash: str = Field(min_length=1)
    finalizer_implementation_manifest_hash: str = Field(min_length=1)
    posthoc_finalizer_fix_applied: bool
    historical_results_reclassified: Literal[False] = False
    pro_api_call_count: Literal[0] = 0
    beneficiary_screening_authorized: Literal[False] = False
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    fresh_confirmation_preparation_authorized: bool
    next_permitted_stage: Literal[
        "fresh_cross_population_stable_confirmation_preparation",
        "stable_support_redesign_only",
        "runtime_conditioned_measurement_repair_only",
    ]
    schema_version: str = CROSS_POPULATION_STABLE_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> FinanceCrossPopulationStableReport:
        if self.recorded_rollout_count != self.requested_rollout_count:
            raise ValueError("cross-population report lacks its complete denominator")
        if len({item.population_id for item in self.population_results}) != 3:
            raise ValueError("cross-population report duplicates a population")
        runtime_ready = all(item.runtime_measurement_ready for item in self.population_results)
        support_ready = all(item.capability_support_admitted for item in self.population_results)
        alignment_ready = all(item.passed for item in self.pairwise_alignments)
        admitted = bool(
            self.static_typed_context_audit_passed
            and runtime_ready
            and support_ready
            and alignment_ready
        )
        if self.all_population_runtime_ready != runtime_ready:
            raise ValueError("cross-population Runtime decision is inconsistent")
        if self.all_population_capability_support_admitted != support_ready:
            raise ValueError("cross-population support decision is inconsistent")
        if self.cross_population_alignment_ready != alignment_ready:
            raise ValueError("cross-population alignment decision is inconsistent")
        if self.development_admitted != admitted:
            raise ValueError("cross-population Development decision is inconsistent")
        if self.fresh_confirmation_preparation_authorized != admitted:
            raise ValueError("cross-population Confirmation permission is inconsistent")
        expected_next = (
            "runtime_conditioned_measurement_repair_only"
            if not (self.static_typed_context_audit_passed and runtime_ready)
            else (
                "fresh_cross_population_stable_confirmation_preparation"
                if admitted
                else "stable_support_redesign_only"
            )
        )
        if self.next_permitted_stage != expected_next:
            raise ValueError("cross-population transition is not fail-closed")
        if self.posthoc_finalizer_fix_applied != (
            self.execution_implementation_manifest_hash
            != self.finalizer_implementation_manifest_hash
        ):
            raise ValueError("cross-population finalizer lineage is inconsistent")
        if self.report_id != cross_population_stable_report_id(self):
            raise ValueError("cross-population report identity is invalid")
        return self


def typed_context_population_audit_id(value: TypedContextPopulationAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_cross_population_typed_context_audit:",
    )


def cross_population_stable_contract_id(
    value: FinanceCrossPopulationStableContract,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="finance_cross_population_stable_support_contract:",
    )


def cross_population_stable_report_id(
    value: FinanceCrossPopulationStableReport,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_cross_population_stable_support_report:",
    )


def typed_retry_contract_rejections(
    value: Mapping[str, Any],
    *,
    available_tool_ids: set[str],
    evidence_ids: set[str] | None = None,
) -> tuple[str, ...]:
    rejections: list[str] = []
    dimensions = value.get("observed_conflict_dimensions")
    if (
        not isinstance(dimensions, list)
        or not dimensions
        or not all(isinstance(item, str) and item.strip() for item in dimensions)
    ):
        rejections.append("missing_conflict_dimensions")
    actions = value.get("available_resolution_actions")
    if not isinstance(actions, list) or len(actions) < 2:
        rejections.append("missing_resolution_actions")
        actions = []
    action_tools: list[str] = []
    for action in actions:
        if not isinstance(action, Mapping):
            rejections.append("malformed_resolution_action")
            continue
        tool_id = action.get("tool_id")
        condition = action.get("applicable_when")
        if not isinstance(tool_id, str) or not tool_id:
            rejections.append("resolution_action_lacks_tool")
            continue
        action_tools.append(tool_id)
        if tool_id not in available_tool_ids:
            rejections.append("unavailable_resolution_action")
        if not isinstance(condition, str) or not condition.strip():
            rejections.append("resolution_action_lacks_condition")
    if len(action_tools) != len(set(action_tools)):
        rejections.append("duplicate_resolution_action")
    decision_rule = value.get("decision_rule")
    if not isinstance(decision_rule, str) or not decision_rule.strip():
        rejections.append("missing_resolution_decision_rule")
    if value.get("required_prerequisite_action") is not None:
        rejections.append("host_selected_required_action")
    if _contains_forbidden_typed_context_key(value):
        rejections.append("host_secret_field_present")
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
    if evidence_ids and any(item in serialized for item in evidence_ids):
        rejections.append("host_evidence_identity_present")
    return tuple(sorted(set(rejections)))


def make_typed_context_population_audit(
    population: CapabilitySubmechanismPopulation,
) -> TypedContextPopulationAudit:
    matches = tuple(
        item for item in population.tasks if item.submechanism_id == UNRESOLVED_CONFLICT_ID
    )
    if len(matches) != 1:
        raise ValueError("population lacks exactly one unresolved-conflict task")
    task = matches[0]
    manifest = make_submechanism_manifest(
        corpus=task.artifact.public_corpus,
        scenario=task.scenario,
        environment_id=f"v25_35:typed_context:{task.artifact.artifact_id}",
        maximum_tool_calls=MAXIMUM_TOOL_CALLS,
        maximum_failed_tool_calls=MAXIMUM_FAILED_TOOL_CALLS,
        maximum_total_observation_bytes=MAXIMUM_OBSERVATION_BYTES,
    )
    runtime = FinanceCapabilitySubmechanismRuntime(
        task.artifact.public_corpus,
        manifest,
        scenario=task.scenario,
    )
    calls = _ReplayCalls(runtime)
    calls.select_all()
    calls.calculate()
    verify_arguments = {
        "evidence_ids": list(runtime.selected_evidence_ids),
        "claim_or_result": {"operation_ref": calls.operation_ref or "operation:pending"},
    }
    trigger_call = AgentToolCall(
        call_index=calls.index + 1,
        tool_id="cross_check_evidence",
        arguments=verify_arguments,
    )
    trigger_result = runtime.execute(trigger_call)
    if trigger_result.status != "failed":
        raise ValueError("typed-context audit did not trigger the conflict state")
    raw_contract = trigger_result.result.get("retry_contract")
    if not isinstance(raw_contract, Mapping):
        raise ValueError("typed-context audit lacks a retry contract")
    retry_contract = dict(raw_contract)
    available_tools = {item.tool_id for item in manifest.tools}
    evidence_ids = {item.evidence_id for item in task.artifact.public_corpus.evidence}
    base_rejections = typed_retry_contract_rejections(
        retry_contract,
        available_tool_ids=available_tools,
        evidence_ids=evidence_ids,
    )
    missing_dimensions = deepcopy(retry_contract)
    missing_dimensions.pop("observed_conflict_dimensions", None)
    reversed_actions = deepcopy(retry_contract)
    actions = list(reversed_actions.get("available_resolution_actions") or [])
    reversed_actions["available_resolution_actions"] = list(reversed(actions))
    unavailable_action = deepcopy(retry_contract)
    unavailable_actions = list(unavailable_action.get("available_resolution_actions") or [])
    unavailable_actions.append(
        {
            "tool_id": "hidden_oracle_conflict_resolver",
            "applicable_when": "the hidden Oracle identifies the correct branch",
        }
    )
    unavailable_action["available_resolution_actions"] = unavailable_actions
    original_observation = make_agent_tool_observation(
        environment_manifest_id=manifest.manifest_id,
        call=trigger_call,
        result=trigger_result,
        observation_time_hash=canonical_hash(
            {"population_id": population.population_id, "step": "typed_trigger"},
            prefix="finance_v25_35_observation_time:",
        ),
    )
    blocked_call = trigger_call.model_copy(update={"call_index": trigger_call.call_index + 1})
    blocked_result = AgentToolResult(
        status="failed",
        result={
            "retry_contract": {
                "policy": ARGUMENT_PATCH_REQUIRED_POLICY,
                "suggested_argument_patch": {
                    "rule": "change at least one argument; the identical action is blocked"
                },
            }
        },
        error_code="identical_failed_action_blocked",
        error_message="The Host blocked an identical failed action.",
    )
    blocked_observation = make_agent_tool_observation(
        environment_manifest_id=manifest.manifest_id,
        call=blocked_call,
        result=blocked_result,
        observation_time_hash=canonical_hash(
            {"population_id": population.population_id, "step": "identical_block"},
            prefix="finance_v25_35_observation_time:",
        ),
    )
    repair = _failed_action_repair_context((original_observation, blocked_observation))
    memory_preserved = bool(
        repair
        and repair.get("repair_source_error_code") == trigger_result.error_code
        and repair.get("observed_conflict_dimensions")
        == retry_contract.get("observed_conflict_dimensions")
        and repair.get("available_resolution_actions")
        == retry_contract.get("available_resolution_actions")
        and repair.get("resolution_decision_rule") == retry_contract.get("decision_rule")
    )
    submechanism_ids = {item.submechanism_id for item in population.tasks}
    covered_shapes = sum(
        bool(set(required) & submechanism_ids) for required in STOPPING_SHAPE_MAPPING.values()
    )
    coverage_rate = covered_shapes / len(STOPPING_SHAPE_MAPPING)
    action_tools = tuple(
        str(item["tool_id"])
        for item in retry_contract.get("available_resolution_actions", [])
        if isinstance(item, Mapping) and isinstance(item.get("tool_id"), str)
    )
    values = {
        "population_id": population.population_id,
        "task_artifact_id": task.artifact.artifact_id,
        "retry_contract_hash": canonical_hash(
            retry_contract, prefix="finance_v25_35_typed_retry_contract:"
        ),
        "action_order_signature": canonical_hash(
            action_tools, prefix="finance_v25_35_action_order:"
        ),
        "action_count": len(action_tools),
        "stopping_shape_coverage_rate": coverage_rate,
        "missing_conflict_dimensions_rejected": bool(
            typed_retry_contract_rejections(
                missing_dimensions,
                available_tool_ids=available_tools,
                evidence_ids=evidence_ids,
            )
        ),
        "action_order_permutation_accepted": not typed_retry_contract_rejections(
            reversed_actions,
            available_tool_ids=available_tools,
            evidence_ids=evidence_ids,
        ),
        "unavailable_distractor_action_rejected": (
            "unavailable_resolution_action"
            in typed_retry_contract_rejections(
                unavailable_action,
                available_tool_ids=available_tools,
                evidence_ids=evidence_ids,
            )
        ),
        "latest_typed_prerequisite_survives_repeated_failure": memory_preserved,
        "host_secret_injection_absent": not base_rejections,
    }
    ready = bool(
        coverage_rate == 1.0
        and all(
            values[key]
            for key in (
                "missing_conflict_dimensions_rejected",
                "action_order_permutation_accepted",
                "unavailable_distractor_action_rejected",
                "latest_typed_prerequisite_survives_repeated_failure",
                "host_secret_injection_absent",
            )
        )
    )
    provisional = TypedContextPopulationAudit.model_construct(
        audit_id="pending", ready=ready, **values
    )
    return TypedContextPopulationAudit(
        audit_id=typed_context_population_audit_id(provisional),
        ready=ready,
        **values,
    )


def prepare_cross_population_stable_contract(
    *,
    protocol_path: Path,
    population_paths: tuple[Path, ...],
    output_path: Path,
    run_id: str,
) -> FinanceCrossPopulationStableContract:
    if output_path.exists():
        raise ValueError("cross-population stable contract is immutable")
    if len(population_paths) != EXPECTED_POPULATION_COUNT:
        raise ValueError("cross-population contract requires exactly three populations")
    protocol_path = protocol_path.resolve()
    protocol = FinanceCrossPopulationStableProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    verify_cross_population_stable_protocol_inputs(protocol)
    calibration_path = Path(protocol.source_stopping_calibration_contract.path).resolve()
    calibration = FinanceStoppingBoundaryCalibrationContract.model_validate_json(
        calibration_path.read_text(encoding="utf-8")
    )
    resolved_population_paths = tuple(item.resolve() for item in population_paths)
    populations = tuple(
        CapabilitySubmechanismPopulation.model_validate_json(path.read_text(encoding="utf-8"))
        for path in resolved_population_paths
    )
    _validate_fresh_populations(protocol, populations, resolved_population_paths)
    task_records = tuple(item for population in populations for item in population.tasks)
    tasks = tuple(item.artifact for item in task_records)
    bindings = tuple(
        _make_runtime_binding(
            task,
            CapabilityRuntimeArm.AUTONOMOUS_AGENT,
            calibration.protocol_profile,
        )
        for task in tasks
    )
    record_by_task = {item.artifact.artifact_id: item for item in task_records}
    population_by_task = {
        item.artifact.artifact_id: population.population_id
        for population in populations
        for item in population.tasks
    }
    task_instances = {
        task_id: canonical_hash(
            {
                "task_record_id": item.task_record_id,
                "semantic_signature": item.source_semantic_signature,
                "materializer_hash": item.materializer_hash,
            },
            prefix="finance_v25_35_task_instance:",
        )
        for task_id, item in record_by_task.items()
    }
    rollout_tokens = {
        f"{binding.binding_id}|{replicate}": canonical_hash(
            {
                "run_id": run_id,
                "binding_id": binding.binding_id,
                "replicate": replicate,
                "task_instance_id": task_instances[binding.task_artifact_id],
            },
            prefix="finance_v25_35_rollout:",
        )
        for binding in bindings
        for replicate in range(REPLICAS)
    }
    model_contracts = tuple(
        item for item in calibration.model_contracts if item.arm == ExplorerArm.FLASH
    )
    if len(model_contracts) != 1:
        raise ValueError("stopping calibration does not freeze exactly one Flash model")
    finance_config = Path(calibration.finance_archive_config_path).resolve()
    implementation = _implementation_manifest()
    references = tuple(
        FrozenArtifactReference(
            path=str(path), sha256=_sha256(path), artifact_id=population.population_id
        )
        for path, population in zip(resolved_population_paths, populations, strict=True)
    )
    audits = tuple(make_typed_context_population_audit(item) for item in populations)
    values = {
        "run_id": run_id,
        "source_protocol": FrozenArtifactReference(
            path=str(protocol_path),
            sha256=_sha256(protocol_path),
            artifact_id=protocol.protocol_id,
        ),
        "source_calibration_contract": FrozenArtifactReference(
            path=str(calibration_path),
            sha256=_sha256(calibration_path),
            artifact_id=calibration.contract_id,
        ),
        "finance_archive_config_path": str(finance_config),
        "finance_archive_config_sha256": _sha256(finance_config),
        "population_references": references,
        "implementation_manifest": implementation,
        "implementation_manifest_hash": canonical_hash(
            implementation,
            prefix="finance_cross_population_stable_support_implementation:",
        ),
        "model_contracts": model_contracts,
        "protocol_profile": calibration.protocol_profile,
        "tasks": tasks,
        "task_submechanism_ids": {
            key: value.submechanism_id for key, value in record_by_task.items()
        },
        "task_parent_mechanism_ids": {
            key: value.parent_mechanism_id for key, value in record_by_task.items()
        },
        "task_raw_capability_demands": _task_demands(populations),
        "task_instance_ids": task_instances,
        "task_population_ids": population_by_task,
        "bindings": bindings,
        "typed_context_audits": audits,
        "maximum_model_tokens_per_rollout": calibration.maximum_model_tokens_per_rollout,
        "maximum_observation_summary_bytes": calibration.maximum_observation_summary_bytes,
        "maximum_public_context_bytes": calibration.maximum_public_context_bytes,
        "model_contract_repair_attempts": calibration.model_contract_repair_attempts,
        "rollout_identity_tokens": rollout_tokens,
        "stable_subspace_policy": protocol.stable_subspace_policy,
    }
    provisional = FinanceCrossPopulationStableContract.model_construct(
        contract_id="pending", **values
    )
    contract = FinanceCrossPopulationStableContract(
        contract_id=cross_population_stable_contract_id(provisional), **values
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(output_path, contract.model_dump(mode="json"))
    return contract


def run_cross_population_stable_support(
    *,
    contract_path: Path,
    output_dir: Path,
    workers: int,
) -> FinanceCrossPopulationStableReport:
    contract = FinanceCrossPopulationStableContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    prefix = "cross_population_stable_development"
    complete_checkpoint = _has_complete_frozen_checkpoint(
        contract,
        output_dir / f"{prefix}.checkpoint.jsonl",
    )
    populations = _verify_contract_inputs(
        contract,
        allow_finalizer_only_change=complete_checkpoint,
    )
    outcomes, discovered = _execute_stage(
        contract=contract,
        tasks={item.artifact_id: item for item in contract.tasks},
        bindings=contract.bindings,
        model_arm=ExplorerArm.FLASH,
        replicas=contract.replicas,
        output_dir=output_dir,
        prefix=prefix,
        workers=workers,
    )
    records_path = output_dir / f"{prefix}_records.jsonl"
    outcomes_path = output_dir / f"{prefix}_outcomes.jsonl"
    records = _load_records(records_path)
    terminals = _make_terminals(contract, records, outcomes)
    expected_host_events = {
        item.artifact.artifact_id: item.scenario.expected_host_events
        for population in populations
        for item in population.tasks
    }
    behavior_contract = contract.model_copy(
        update={"task_expected_host_events": expected_host_events}
    )
    behaviors = make_submechanism_behavior_observations(
        cast(Any, behavior_contract), records, outcomes, terminals
    )
    terminal_path = output_dir / f"{prefix}_terminal_outcomes.jsonl"
    behavior_path = output_dir / f"{prefix}_behavior_observations.jsonl"
    _write_jsonl_atomic(terminal_path, (item.model_dump(mode="json") for item in terminals))
    _write_jsonl_atomic(behavior_path, (item.model_dump(mode="json") for item in behaviors))
    report = make_cross_population_stable_report(
        contract,
        populations,
        records,
        outcomes,
        terminals,
        behaviors,
        discovered_models=discovered,
    )
    report_path = output_dir / "finance_cross_population_stable_support_report.json"
    _write_json_atomic(report_path, report.model_dump(mode="json"))
    _write_text_atomic(
        output_dir / "finance_cross_population_stable_support_report.md",
        _render_report(report),
    )
    manifest = {
        "schema_version": CROSS_POPULATION_STABLE_MANIFEST_VERSION,
        "contract_id": contract.contract_id,
        "report_id": report.report_id,
        "requested_model": contract.model_contracts[0].requested_model,
        "discovered_models": discovered,
        "records_sha256": _sha256(records_path),
        "outcomes_sha256": _sha256(outcomes_path),
        "terminal_outcomes_sha256": _sha256(terminal_path),
        "behavior_observations_sha256": _sha256(behavior_path),
        "report_sha256": _sha256(report_path),
        "execution_implementation_manifest_hash": (
            report.execution_implementation_manifest_hash
        ),
        "finalizer_implementation_manifest_hash": (
            report.finalizer_implementation_manifest_hash
        ),
        "posthoc_finalizer_fix_applied": report.posthoc_finalizer_fix_applied,
        "pooled_result_used_for_admission": False,
        "fresh_confirmation_preparation_authorized": (
            report.fresh_confirmation_preparation_authorized
        ),
        "pro_api_call_count": 0,
        "beneficiary_screening_authorized": False,
        "exact_target_evaluated": False,
        "gp_c_evaluated": False,
        "production_contribution": 0.0,
    }
    _write_json_atomic(
        output_dir / "finance_cross_population_stable_support_manifest.json",
        manifest,
    )
    return report


def make_cross_population_stable_report(
    contract: FinanceCrossPopulationStableContract,
    populations: Sequence[CapabilitySubmechanismPopulation],
    records: Sequence[CapabilityBoundaryRolloutRecord],
    outcomes: Sequence[CapabilityRolloutOutcome],
    terminals: Sequence[RuntimeTerminalOutcome],
    behaviors: Sequence[SubmechanismBehaviorObservation],
    *,
    discovered_models: Sequence[str],
) -> FinanceCrossPopulationStableReport:
    if not (
        len(records)
        == len(outcomes)
        == len(terminals)
        == len(behaviors)
        == contract.requested_rollout_count
    ):
        raise ValueError("cross-population report has an incomplete denominator")
    results: list[PopulationStableResult] = []
    rows_by_population: dict[str, tuple[StableTaskResponse, ...]] = {}
    for index, population in enumerate(populations):
        task_ids = {
            task_id
            for task_id, population_id in contract.task_population_ids.items()
            if population_id == population.population_id
        }
        population_terminals = tuple(
            item for item in terminals if item.task_artifact_id in task_ids
        )
        population_behaviors = tuple(
            item for item in behaviors if item.task_artifact_id in task_ids
        )
        population_records = tuple(item for item in records if item.task_artifact_id in task_ids)
        rows, complete = _stable_rows(contract, population_behaviors)
        estimate = estimate_stable_subspace(rows, contract.stable_subspace_policy)
        bootstrap = bootstrap_stable_subspace(
            rows,
            contract.stable_subspace_policy,
            seed_offset=(index + 1) * 100_000,
        )
        typed_context = make_typed_context_dynamic_summary(population, population_records)
        result = _make_population_result(
            contract,
            population,
            population_terminals,
            estimate,
            bootstrap,
            typed_context,
            complete_task_count=len(complete),
        )
        results.append(result)
        rows_by_population[population.population_id] = rows
    alignments: list[CrossPopulationAlignmentResult] = []
    for left_index, left in enumerate(populations):
        for right in populations[left_index + 1 :]:
            alignment = compare_stable_subspaces(
                rows_by_population[left.population_id],
                rows_by_population[right.population_id],
                contract.stable_subspace_policy,
            )
            passed = bool(
                alignment.maximum_principal_angle_degrees
                <= contract.stable_subspace_policy.maximum_principal_angle_degrees
                and alignment.bootstrap_alignment_pass_rate
                >= contract.stable_subspace_policy.minimum_bootstrap_alignment_rate
            )
            alignments.append(
                CrossPopulationAlignmentResult(
                    left_population_id=left.population_id,
                    right_population_id=right.population_id,
                    alignment=alignment,
                    passed=passed,
                )
            )
    pooled_rows = tuple(
        item for population in populations for item in rows_by_population[population.population_id]
    )
    pooled_estimate = estimate_stable_subspace(pooled_rows, contract.stable_subspace_policy)
    pooled_bootstrap = bootstrap_stable_subspace(
        pooled_rows,
        contract.stable_subspace_policy,
        seed_offset=900_000,
    )
    static_ready = all(item.ready for item in contract.typed_context_audits)
    runtime_ready = all(item.runtime_measurement_ready for item in results)
    support_ready = all(item.capability_support_admitted for item in results)
    alignment_ready = all(item.passed for item in alignments)
    admitted = bool(static_ready and runtime_ready and support_ready and alignment_ready)
    failures = tuple(
        [f"{item.population_id}:{code}" for item in results for code in item.failure_codes]
        + [
            f"alignment:{item.left_population_id}:{item.right_population_id}"
            for item in alignments
            if not item.passed
        ]
    )
    values = {
        "contract_id": contract.contract_id,
        "recorded_rollout_count": len(records),
        "population_results": tuple(results),
        "pairwise_alignments": tuple(alignments),
        "pooled_diagnostic_estimate": pooled_estimate,
        "pooled_diagnostic_bootstrap": pooled_bootstrap,
        "static_typed_context_audit_passed": static_ready,
        "all_population_runtime_ready": runtime_ready,
        "all_population_capability_support_admitted": support_ready,
        "cross_population_alignment_ready": alignment_ready,
        "development_admitted": admitted,
        "failure_codes": failures,
        "outcome_set_hash": canonical_hash(
            tuple(item.terminal_outcome_id for item in terminals),
            prefix="finance_v25_35_terminal_set:",
        ),
        "behavior_set_hash": canonical_hash(
            tuple(item.observation_id for item in behaviors),
            prefix="finance_v25_35_behavior_set:",
        ),
        "api_call_count": sum(item.api_call_count for item in outcomes),
        "total_model_tokens": sum(item.total_model_tokens for item in outcomes),
        "estimated_cost_usd": sum(item.estimated_cost_usd for item in outcomes),
        "discovered_models": tuple(discovered_models),
        "execution_implementation_manifest_hash": (
            contract.implementation_manifest_hash
        ),
        "finalizer_implementation_manifest_hash": canonical_hash(
            _implementation_manifest(),
            prefix="finance_cross_population_stable_support_implementation:",
        ),
        "posthoc_finalizer_fix_applied": (
            _implementation_manifest() != contract.implementation_manifest
        ),
        "fresh_confirmation_preparation_authorized": admitted,
        "next_permitted_stage": (
            "runtime_conditioned_measurement_repair_only"
            if not (static_ready and runtime_ready)
            else (
                "fresh_cross_population_stable_confirmation_preparation"
                if admitted
                else "stable_support_redesign_only"
            )
        ),
    }
    provisional = FinanceCrossPopulationStableReport.model_construct(report_id="pending", **values)
    return FinanceCrossPopulationStableReport(
        report_id=cross_population_stable_report_id(provisional), **values
    )


def make_typed_context_dynamic_summary(
    population: CapabilitySubmechanismPopulation,
    records: Sequence[CapabilityBoundaryRolloutRecord],
) -> TypedContextDynamicSummary:
    task = next(item for item in population.tasks if item.submechanism_id == UNRESOLVED_CONFLICT_ID)
    task_records = tuple(
        item for item in records if item.task_artifact_id == task.artifact.artifact_id
    )
    manifest = make_submechanism_manifest(
        corpus=task.artifact.public_corpus,
        scenario=task.scenario,
        environment_id=f"v25_35:dynamic_replay:{task.artifact.artifact_id}",
        maximum_tool_calls=MAXIMUM_TOOL_CALLS,
        maximum_failed_tool_calls=MAXIMUM_FAILED_TOOL_CALLS,
        maximum_total_observation_bytes=MAXIMUM_OBSERVATION_BYTES,
    )
    available_tools = {item.tool_id for item in manifest.tools}
    evidence_ids = {item.evidence_id for item in task.artifact.public_corpus.evidence}
    trigger_count = 0
    complete_count = 0
    identical_count = 0
    preserved_count = 0
    for record in task_records:
        observations = _all_observations(record)
        typed_indices = [
            index
            for index, observation in enumerate(observations)
            if _typed_retry_contract(observation) is not None
        ]
        if typed_indices:
            trigger_count += 1
        replay_complete = bool(typed_indices)
        for index in typed_indices:
            retry_contract = _typed_retry_contract(observations[index])
            assert retry_contract is not None
            if typed_retry_contract_rejections(
                retry_contract,
                available_tool_ids=available_tools,
                evidence_ids=evidence_ids,
            ):
                replay_complete = False
        for index, observation in enumerate(observations):
            if observation.error_code != "identical_failed_action_blocked":
                continue
            if not any(value < index for value in typed_indices):
                continue
            identical_count += 1
            context = _failed_action_repair_context(tuple(observations[: index + 1]))
            if _repair_context_preserves_typed_contract(context, observations, index):
                preserved_count += 1
            else:
                replay_complete = False
        if replay_complete:
            complete_count += 1
    return TypedContextDynamicSummary(
        trigger_observed_rollout_count=trigger_count,
        complete_replay_rollout_count=complete_count,
        complete_replay_rate=(
            complete_count / EXPECTED_UNRESOLVED_CONFLICT_ROLLOUTS_PER_POPULATION
        ),
        identical_block_count=identical_count,
        identical_block_memory_preserved_count=preserved_count,
    )


def _make_population_result(
    contract: FinanceCrossPopulationStableContract,
    population: CapabilitySubmechanismPopulation,
    terminals: Sequence[RuntimeTerminalOutcome],
    estimate: StableSubspaceEstimate,
    bootstrap: StableBootstrapSummary,
    typed_context: TypedContextDynamicSummary,
    *,
    complete_task_count: int,
) -> PopulationStableResult:
    execution = _rate(item.execution_integrity_passed for item in terminals)
    terminal_resolution = _rate(item.terminal_resolved for item in terminals)
    api = _rate(item.api_transport_resolved for item in terminals)
    bounded_json = _rate(item.bounded_json_resolution_success for item in terminals)
    replay = _rate(item.observation_replay_success for item in terminals)
    authority = _rate(item.authority_integrity_success for item in terminals)
    pathology = _rate(item.runtime_pathology for item in terminals)
    l0_l2 = sum(
        item.primary_failure_layer
        in {
            FailureLayer.L0_EXTERNAL_INFRASTRUCTURE,
            FailureLayer.L1_TASK_RUNTIME_CONTRACT,
            FailureLayer.L2_TOOL_ENVIRONMENT,
        }
        for item in terminals
    )
    stopping_share = estimate.parent_information_share.get(STOPPING_PARENT_ID, 0.0)
    stopping_lcb = bootstrap.parent_share_interval95.get(STOPPING_PARENT_ID, (0.0, 0.0))[0]
    stopping_nonzero = estimate.nonzero_task_count_by_parent.get(STOPPING_PARENT_ID, 0)
    gates = _population_gates(
        contract.stable_subspace_policy,
        terminal_count=len(terminals),
        complete_task_count=complete_task_count,
        execution_integrity=execution,
        terminal_resolution=terminal_resolution,
        api_transport=api,
        bounded_json=bounded_json,
        observation_replay=replay,
        authority_integrity=authority,
        runtime_pathology=pathology,
        l0_l2_failure_count=l0_l2,
        typed_context=typed_context,
        estimate=estimate,
        bootstrap=bootstrap,
        stopping_share=stopping_share,
        stopping_lcb=stopping_lcb,
        stopping_nonzero=stopping_nonzero,
    )
    runtime_ready = all(
        item.passed for item in gates if item.category in {"runtime", "typed_context"}
    )
    admitted = runtime_ready and all(
        item.passed for item in gates if item.category not in {"runtime", "typed_context"}
    )
    return PopulationStableResult(
        population_id=population.population_id,
        task_count=estimate.task_count,
        rollout_count=len(terminals),
        execution_integrity_rate=execution,
        terminal_resolution_rate=terminal_resolution,
        api_transport_resolution_rate=api,
        bounded_json_resolution_rate=bounded_json,
        observation_replay_rate=replay,
        authority_integrity_rate=authority,
        runtime_pathology_rate=pathology,
        l0_l2_failure_count=l0_l2,
        typed_context=typed_context,
        stable_estimate=estimate,
        bootstrap_summary=bootstrap,
        stopping_parent_information_share=stopping_share,
        stopping_parent_bootstrap_lcb=stopping_lcb,
        nonzero_stopping_task_count=stopping_nonzero,
        gates=gates,
        runtime_measurement_ready=runtime_ready,
        capability_support_admitted=admitted,
        failure_codes=tuple(item.gate_id for item in gates if not item.passed),
    )


def _population_gates(
    policy: StableIdentifiableSubspacePolicy,
    *,
    terminal_count: int,
    complete_task_count: int,
    execution_integrity: float,
    terminal_resolution: float,
    api_transport: float,
    bounded_json: float,
    observation_replay: float,
    authority_integrity: float,
    runtime_pathology: float,
    l0_l2_failure_count: int,
    typed_context: TypedContextDynamicSummary,
    estimate: StableSubspaceEstimate,
    bootstrap: StableBootstrapSummary,
    stopping_share: float,
    stopping_lcb: float,
    stopping_nonzero: int,
) -> tuple[PopulationStableGate, ...]:
    rows: tuple[tuple[str, PopulationGateCategory, float, bool, str], ...] = (
        (
            "complete_rollout_denominator",
            "runtime",
            float(terminal_count),
            terminal_count == EXPECTED_ROLLOUTS_PER_POPULATION,
            f"={EXPECTED_ROLLOUTS_PER_POPULATION}",
        ),
        (
            "execution_integrity_rate",
            "runtime",
            execution_integrity,
            execution_integrity == 1.0,
            "=1",
        ),
        (
            "terminal_resolution_rate",
            "runtime",
            terminal_resolution,
            terminal_resolution == 1.0,
            "=1",
        ),
        ("api_transport_resolution_rate", "runtime", api_transport, api_transport == 1.0, "=1"),
        ("bounded_json_resolution_rate", "runtime", bounded_json, bounded_json == 1.0, "=1"),
        ("observation_replay_rate", "runtime", observation_replay, observation_replay == 1.0, "=1"),
        (
            "authority_integrity_rate",
            "runtime",
            authority_integrity,
            authority_integrity == 1.0,
            "=1",
        ),
        ("runtime_pathology_rate", "runtime", runtime_pathology, runtime_pathology == 0.0, "=0"),
        (
            "l0_l2_failure_count",
            "runtime",
            float(l0_l2_failure_count),
            l0_l2_failure_count == 0,
            "=0",
        ),
        (
            "complete_runtime_task_denominator",
            "runtime",
            float(complete_task_count),
            complete_task_count == EXPECTED_TASKS_PER_POPULATION,
            f"={EXPECTED_TASKS_PER_POPULATION}",
        ),
        (
            "typed_context_trigger_denominator",
            "typed_context",
            float(typed_context.trigger_observed_rollout_count),
            typed_context.trigger_observed_rollout_count
            == EXPECTED_UNRESOLVED_CONFLICT_ROLLOUTS_PER_POPULATION,
            f"={EXPECTED_UNRESOLVED_CONFLICT_ROLLOUTS_PER_POPULATION}",
        ),
        (
            "typed_context_complete_replay_rate",
            "typed_context",
            typed_context.complete_replay_rate,
            typed_context.complete_replay_rate == 1.0,
            "=1",
        ),
        (
            "geometry_task_denominator",
            "coverage",
            float(estimate.task_count),
            estimate.task_count == EXPECTED_TASKS_PER_POPULATION,
            f"={EXPECTED_TASKS_PER_POPULATION}",
        ),
        (
            "geometry_rollout_denominator",
            "coverage",
            float(estimate.rollout_count),
            estimate.rollout_count == EXPECTED_ROLLOUTS_PER_POPULATION,
            f"={EXPECTED_ROLLOUTS_PER_POPULATION}",
        ),
        (
            "nonzero_weight_task_count",
            "geometry",
            float(estimate.nonzero_weight_task_count),
            estimate.nonzero_weight_task_count >= policy.minimum_nonzero_weight_task_count,
            f">={policy.minimum_nonzero_weight_task_count}",
        ),
        (
            "boundary_task_fraction",
            "geometry",
            estimate.boundary_task_fraction,
            estimate.boundary_task_fraction >= policy.minimum_boundary_task_fraction,
            f">={policy.minimum_boundary_task_fraction}",
        ),
        (
            "identifiable_rank",
            "geometry",
            float(estimate.identifiable_rank),
            estimate.identifiable_rank >= policy.required_rank,
            f">={policy.required_rank}",
        ),
        (
            "top4_effective_rank",
            "geometry",
            estimate.claimed_effective_rank,
            estimate.claimed_effective_rank >= policy.minimum_effective_rank,
            f">={policy.minimum_effective_rank}",
        ),
        (
            "top4_condition_number",
            "geometry",
            estimate.claimed_condition_number,
            estimate.claimed_condition_number <= policy.maximum_condition_number,
            f"<={policy.maximum_condition_number}",
        ),
        (
            "bootstrap_joint_geometry_pass_rate",
            "geometry",
            bootstrap.joint_geometry_pass_rate,
            bootstrap.joint_geometry_pass_rate >= policy.minimum_bootstrap_geometry_pass_rate,
            f">={policy.minimum_bootstrap_geometry_pass_rate}",
        ),
        (
            "general_factor_fraction",
            "geometry",
            estimate.general_factor_fraction,
            estimate.general_factor_fraction <= policy.maximum_general_factor_fraction,
            f"<={policy.maximum_general_factor_fraction}",
        ),
        (
            "informative_axis_count",
            "geometry",
            float(estimate.informative_axis_count),
            estimate.informative_axis_count >= policy.minimum_informative_axis_count,
            f">={policy.minimum_informative_axis_count}",
        ),
        (
            "minimum_parent_information_share",
            "geometry",
            estimate.minimum_parent_information_share,
            estimate.minimum_parent_information_share >= policy.minimum_parent_information_share,
            f">={policy.minimum_parent_information_share}",
        ),
        (
            "maximum_parent_information_share",
            "geometry",
            estimate.maximum_parent_information_share,
            estimate.maximum_parent_information_share <= policy.maximum_parent_information_share,
            f"<={policy.maximum_parent_information_share}",
        ),
        (
            "minimum_parent_share_bootstrap_lcb",
            "geometry",
            bootstrap.minimum_parent_share_lcb,
            bootstrap.minimum_parent_share_lcb >= policy.minimum_parent_share_bootstrap_lcb,
            f">={policy.minimum_parent_share_bootstrap_lcb}",
        ),
        (
            "minimum_nonzero_tasks_per_parent",
            "geometry",
            float(min(estimate.nonzero_task_count_by_parent.values(), default=0)),
            min(estimate.nonzero_task_count_by_parent.values(), default=0)
            >= policy.minimum_nonzero_tasks_per_parent,
            f">={policy.minimum_nonzero_tasks_per_parent}",
        ),
        (
            "stopping_parent_information_share",
            "stopping_parent",
            stopping_share,
            stopping_share >= policy.minimum_parent_information_share,
            f">={policy.minimum_parent_information_share}",
        ),
        (
            "stopping_parent_bootstrap_lcb_strictly_positive",
            "stopping_parent",
            stopping_lcb,
            stopping_lcb > 0.0,
            ">0",
        ),
        (
            "nonzero_stopping_task_count",
            "stopping_parent",
            float(stopping_nonzero),
            stopping_nonzero >= policy.minimum_nonzero_tasks_per_parent,
            f">={policy.minimum_nonzero_tasks_per_parent}",
        ),
    )
    return tuple(
        PopulationStableGate(
            gate_id=gate_id,
            category=category,
            observed=observed,
            passed=passed,
            requirement=requirement,
        )
        for gate_id, category, observed, passed, requirement in rows
    )


def _typed_retry_contract(
    observation: AgentToolObservation,
) -> dict[str, Any] | None:
    raw = observation.result.get("retry_contract")
    if not isinstance(raw, dict):
        return None
    if not (raw.get("observed_conflict_dimensions") or raw.get("available_resolution_actions")):
        return None
    return raw


def _repair_context_preserves_typed_contract(
    context: Mapping[str, Any] | None,
    observations: Sequence[AgentToolObservation],
    blocked_index: int,
) -> bool:
    if context is None:
        return False
    source = next(
        (
            _typed_retry_contract(item)
            for item in reversed(observations[:blocked_index])
            if _typed_retry_contract(item) is not None
        ),
        None,
    )
    return bool(
        source
        and context.get("observed_conflict_dimensions")
        == source.get("observed_conflict_dimensions")
        and context.get("available_resolution_actions")
        == source.get("available_resolution_actions")
        and context.get("resolution_decision_rule") == source.get("decision_rule")
    )


def _validate_fresh_populations(
    protocol: FinanceCrossPopulationStableProtocol,
    populations: Sequence[CapabilitySubmechanismPopulation],
    population_paths: Sequence[Path],
) -> None:
    if len(populations) != EXPECTED_POPULATION_COUNT:
        raise ValueError("v25.35 requires three fresh populations")
    if any(not item.static_audit.ready for item in populations):
        raise ValueError("v25.35 population failed its static audit")
    expected_submechanisms = {item.submechanism_id for item in populations[0].tasks}
    if len(expected_submechanisms) != EXPECTED_TASKS_PER_POPULATION:
        raise ValueError("v25.35 population lacks 20 submechanisms")
    if any(
        {item.submechanism_id for item in population.tasks} != expected_submechanisms
        for population in populations[1:]
    ):
        raise ValueError("v25.35 populations changed the submechanism catalog")
    if any(
        task.scenario.schema_version != FINANCE_SUBMECHANISM_SCENARIO_VERSION
        for population in populations
        for task in population.tasks
    ):
        raise ValueError("v25.35 population was built with an obsolete Runtime scenario")
    for left_index, left in enumerate(populations):
        for right in populations[left_index + 1 :]:
            disjoint = _population_disjointness(left, right)
            if not all(disjoint.values()):
                raise ValueError(f"v25.35 fresh populations overlap:{disjoint}")
    historical = tuple(
        json.loads(Path(reference.path).read_text(encoding="utf-8"))
        for reference in protocol.historical_population_references
    )
    historical_paths = {
        str(Path(reference.path).resolve())
        for reference in protocol.historical_population_references
    }
    for index, population in enumerate(populations):
        frozen_exclusions = {str(Path(item).resolve()) for item in population.exclusion_paths}
        required_exclusions = historical_paths | {
            str(item.resolve()) for item in population_paths[:index]
        }
        if not required_exclusions <= frozen_exclusions:
            raise ValueError("v25.35 population omits a required historical exclusion")
        current_identity = _population_identity_payload(
            population.model_dump(mode="json")
        )
        for prior in historical:
            prior_identity = _population_identity_payload(prior)
            disjoint = {
                key: not bool(current_identity[key] & prior_identity[key])
                for key in current_identity
            }
            if not all(disjoint.values()):
                raise ValueError(f"v25.35 population overlaps history:{disjoint}")


def _task_demands(
    populations: Sequence[CapabilitySubmechanismPopulation],
) -> dict[str, dict[str, float]]:
    direction_path = Path(populations[0].source_direction_report_path)
    direction = CapabilitySubmechanismDirectionReport.model_validate_json(
        direction_path.read_text(encoding="utf-8")
    )
    if any(item.source_direction_report_id != direction.report_id for item in populations):
        raise ValueError("v25.35 populations changed the Direction Report")
    selected = set(direction.selected_submechanism_ids)
    specs = {
        item.submechanism_id: item
        for item in direction.candidate_specs
        if item.submechanism_id in selected
    }
    return {
        task.artifact.artifact_id: specs[task.submechanism_id].raw_capability_demand
        for population in populations
        for task in population.tasks
    }


def _verify_contract_inputs(
    contract: FinanceCrossPopulationStableContract,
    *,
    allow_finalizer_only_change: bool = False,
) -> tuple[CapabilitySubmechanismPopulation, ...]:
    if _sha256(Path(contract.source_protocol.path)) != contract.source_protocol.sha256:
        raise ValueError("v25.35 frozen protocol changed")
    if (
        _sha256(Path(contract.source_calibration_contract.path))
        != contract.source_calibration_contract.sha256
    ):
        raise ValueError("v25.35 stopping-calibration contract changed")
    if (
        _sha256(Path(contract.finance_archive_config_path))
        != contract.finance_archive_config_sha256
    ):
        raise ValueError("v25.35 Finance Archive config changed")
    current_implementation = _implementation_manifest()
    if current_implementation != contract.implementation_manifest and not (
        allow_finalizer_only_change
        and _only_finalizer_changed(
            contract.implementation_manifest, current_implementation
        )
    ):
        raise ValueError("v25.35 implementation changed after contract freeze")
    protocol = FinanceCrossPopulationStableProtocol.model_validate_json(
        Path(contract.source_protocol.path).read_text(encoding="utf-8")
    )
    verify_cross_population_stable_protocol_inputs(protocol)
    if protocol.protocol_id != contract.source_protocol.artifact_id:
        raise ValueError("v25.35 protocol identity changed")
    calibration = FinanceStoppingBoundaryCalibrationContract.model_validate_json(
        Path(contract.source_calibration_contract.path).read_text(encoding="utf-8")
    )
    if calibration.contract_id != contract.source_calibration_contract.artifact_id:
        raise ValueError("v25.35 calibration identity changed")
    populations = tuple(
        CapabilitySubmechanismPopulation.model_validate_json(
            Path(reference.path).read_text(encoding="utf-8")
        )
        for reference in contract.population_references
    )
    for reference, population in zip(contract.population_references, populations, strict=True):
        if _sha256(Path(reference.path)) != reference.sha256:
            raise ValueError("v25.35 frozen population changed")
        if population.population_id != reference.artifact_id:
            raise ValueError("v25.35 population identity changed")
    _validate_fresh_populations(
        protocol,
        populations,
        tuple(Path(item.path) for item in contract.population_references),
    )
    recomputed_audits = tuple(make_typed_context_population_audit(item) for item in populations)
    if recomputed_audits != contract.typed_context_audits:
        raise ValueError("v25.35 typed-context audit changed after freeze")
    return populations


def _has_complete_frozen_checkpoint(
    contract: FinanceCrossPopulationStableContract,
    path: Path,
) -> bool:
    if not path.is_file():
        return False
    records = tuple(
        CapabilityBoundaryRolloutRecord.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    expected = {
        (binding.binding_id, replicate)
        for binding in contract.bindings
        for replicate in range(contract.replicas)
    }
    observed = {(item.binding_id, item.replicate) for item in records}
    return bool(
        len(records) == contract.requested_rollout_count
        and observed == expected
        and all(item.contract_id == contract.contract_id for item in records)
    )


def _only_finalizer_changed(
    frozen: Mapping[str, str],
    current: Mapping[str, str],
) -> bool:
    finalizer_path = str(Path(__file__).resolve().relative_to(Path(__file__).parents[4]))
    return bool(
        set(frozen) == set(current)
        and frozen.get(finalizer_path) != current.get(finalizer_path)
        and all(
            frozen[path] == current[path]
            for path in frozen
            if path != finalizer_path
        )
    )


def _contains_forbidden_typed_context_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            (str(key).lower() in _FORBIDDEN_TYPED_CONTEXT_KEYS and nested is not None)
            or _contains_forbidden_typed_context_key(nested)
            for key, nested in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_forbidden_typed_context_key(item) for item in value)
    return False


def _population_identity_payload(value: Any) -> dict[str, set[str]]:
    identities: dict[str, set[str]] = {
        "evidence": set(),
        "evidence_version": set(),
        "task": set(),
        "semantic_signature": set(),
        "submechanism_signature_instance": set(),
    }
    if not isinstance(value, Mapping):
        return identities
    raw_tasks = value.get("tasks")
    if not isinstance(raw_tasks, list):
        return identities
    for raw_task in raw_tasks:
        if not isinstance(raw_task, Mapping):
            continue
        semantic = raw_task.get("source_semantic_signature")
        materializer = raw_task.get("materializer_hash")
        if isinstance(semantic, str):
            identities["semantic_signature"].add(semantic)
        if isinstance(materializer, str):
            identities["submechanism_signature_instance"].add(materializer)
        artifact = raw_task.get("artifact")
        if not isinstance(artifact, Mapping):
            continue
        task = artifact.get("task")
        if isinstance(task, Mapping) and isinstance(task.get("task_id"), str):
            identities["task"].add(str(task["task_id"]))
        corpus = artifact.get("public_corpus")
        evidence = corpus.get("evidence") if isinstance(corpus, Mapping) else None
        if not isinstance(evidence, list):
            continue
        for item in evidence:
            if not isinstance(item, Mapping):
                continue
            if isinstance(item.get("evidence_id"), str):
                identities["evidence"].add(str(item["evidence_id"]))
            if isinstance(item.get("evidence_version_id"), str):
                identities["evidence_version"].add(str(item["evidence_version_id"]))
    return identities


def _implementation_manifest() -> dict[str, str]:
    root = Path(__file__).resolve().parents[4]
    paths = (
        Path(__file__).resolve(),
        root
        / (
            "src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_cross_population_stable_protocol.py"
        ),
        root
        / (
            "src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_stable_submechanism_geometry.py"
        ),
        root
        / (
            "src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_capability_submechanism_population.py"
        ),
        root
        / (
            "src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_capability_submechanism_flash_development.py"
        ),
        root / "src/trusted_synthesis/experiments/vtdo_experiment/phase1_multitier_confirmation.py",
        root
        / (
            "src/trusted_synthesis/experiments/vtdo_experiment/"
            "phase1_multitier_runtime_resolution.py"
        ),
        root / "src/trusted_synthesis/domains/finance/capability_submechanism_runtime.py",
        root / "src/trusted_synthesis/runtime/agent/iterative.py",
        root / "src/trusted_synthesis/runtime/agent/client.py",
        root / "src/trusted_synthesis/runtime/agent/llm_agent.py",
        root / "src/trusted_synthesis/domains/finance/iterative_agent_verifier.py",
    )
    return {str(path.relative_to(root)): _sha256(path) for path in paths}


def _rate(values: Iterable[bool]) -> float:
    rows = tuple(values)
    return sum(rows) / len(rows) if rows else 0.0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_atomic(path: Path, value: object) -> None:
    _write_text_atomic(
        path,
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def _write_jsonl_atomic(path: Path, values: Iterable[Mapping[str, Any]]) -> None:
    _write_text_atomic(
        path,
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in values),
    )


def _write_text_atomic(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def _render_report(report: FinanceCrossPopulationStableReport) -> str:
    population_rows = tuple(
        (
            f"| {index} | {item.runtime_measurement_ready} | "
            f"{item.capability_support_admitted} | "
            f"{item.stable_estimate.boundary_task_fraction:.2%} | "
            f"{item.nonzero_stopping_task_count} | "
            f"{item.stopping_parent_information_share:.2%} | "
            f"{item.stopping_parent_bootstrap_lcb:.2%} | "
            f"{item.stable_estimate.identifiable_rank} | "
            f"{item.stable_estimate.claimed_effective_rank:.3f} | "
            f"{item.stable_estimate.claimed_condition_number:.3f} |"
        )
        for index, item in enumerate(report.population_results, start=1)
    )
    alignment_rows = tuple(
        (
            f"| {index} | {item.alignment.maximum_principal_angle_degrees:.3f} | "
            f"{item.alignment.bootstrap_alignment_pass_rate:.2%} | {item.passed} |"
        )
        for index, item in enumerate(report.pairwise_alignments, start=1)
    )
    return "\n".join(
        (
            "# Finance v25.35 Cross-population Stable-support Development",
            "",
            "## Decision",
            "",
            f"- Report ID: `{report.report_id}`",
            f"- Complete denominator: **{report.recorded_rollout_count}/480**",
            f"- Static typed-context audit: **{report.static_typed_context_audit_passed}**",
            f"- All populations Runtime-ready: **{report.all_population_runtime_ready}**",
            (
                "- All populations support-admitted: "
                f"**{report.all_population_capability_support_admitted}**"
            ),
            f"- Pairwise subspace alignment: **{report.cross_population_alignment_ready}**",
            f"- Development admitted: **{report.development_admitted}**",
            f"- Next permitted stage: `{report.next_permitted_stage}`",
            "- Pooled result used for admission: **False**",
            "",
            "## Per-population Evidence",
            "",
            (
                "| Population | Runtime | Support | Boundary | Nonzero Stop | "
                "Stop Share | Stop LCB | Rank | Eff. Rank | Cond. |"
            ),
            "| ---: | :---: | :---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            *population_rows,
            "",
            "## Pairwise Top-4 Alignment",
            "",
            "| Pair | Max angle | Bootstrap pass | Passed |",
            "| ---: | ---: | ---: | :---: |",
            *alignment_rows,
            "",
            "The pooled estimate is diagnostic only and cannot rescue a failed population.",
            "v25.33 remains a frozen failure; v25.34 remains an instrument calibration.",
            "Pro, Beneficiary, Exact Target, GP-C, and Contribution were not run.",
            "",
        )
    )


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare or run v25.35 cross-population stable support"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--protocol", required=True, type=Path)
    prepare.add_argument("--population", action="append", required=True, type=Path)
    prepare.add_argument("--output-path", required=True, type=Path)
    prepare.add_argument("--run-id", required=True)
    run = commands.add_parser("run")
    run.add_argument("--contract", required=True, type=Path)
    run.add_argument("--output-dir", required=True, type=Path)
    run.add_argument("--workers", type=int, default=24)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.command == "prepare":
        contract = prepare_cross_population_stable_contract(
            protocol_path=args.protocol,
            population_paths=tuple(args.population),
            output_path=args.output_path,
            run_id=args.run_id,
        )
        summary: dict[str, Any] = {
            "contract_id": contract.contract_id,
            "population_count": len(contract.population_references),
            "task_count": len(contract.tasks),
            "requested_rollout_count": contract.requested_rollout_count,
            "static_typed_context_ready": all(item.ready for item in contract.typed_context_audits),
            "next_permitted_stage": contract.next_permitted_stage,
        }
    else:
        report = run_cross_population_stable_support(
            contract_path=args.contract,
            output_dir=args.output_dir,
            workers=args.workers,
        )
        summary = {
            "report_id": report.report_id,
            "recorded_rollout_count": report.recorded_rollout_count,
            "all_population_runtime_ready": report.all_population_runtime_ready,
            "all_population_capability_support_admitted": (
                report.all_population_capability_support_admitted
            ),
            "cross_population_alignment_ready": (report.cross_population_alignment_ready),
            "development_admitted": report.development_admitted,
            "next_permitted_stage": report.next_permitted_stage,
        }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
